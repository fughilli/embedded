// swd_bridge: a CMSIS-DAP probe served over elaphureLink (TCP), bit-banging SWD on
// Raspberry Pi 5 GPIO. pyOCD reaches it through //tools/pyocd's `elaphurelink` probe type:
//   pyocd commander -u elaphurelink:<pi-host> -t stm32h757ziyx
//
// elaphureLink: after a 12-byte handshake (big-endian identifier 0x8a656c70, command 0,
// version), each message is one raw CMSIS-DAP command, answered by one raw response.
#include <arpa/inet.h>
#include <errno.h>
#include <getopt.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include "DAP_config.h"
#include "DAP.h"
#include "rp1_gpio.h"

#define EL_LINK_IDENTIFIER 0x8a656c70u
#define EL_COMMAND_HANDSHAKE 0u
#define EL_DAP_VERSION 1u

uint32_t swd_clk_mask;
uint32_t swd_dio_mask;
uint32_t swd_nreset_mask;
char swd_serial[64];

static void on_signal(int sig) {
  PORT_OFF();
  rp1_restore_all();
  signal(sig, SIG_DFL);
  raise(sig);
}

static int recv_exact(int fd, uint8_t *buf, size_t len) {
  size_t got = 0;
  while (got < len) {
    ssize_t n = recv(fd, buf + got, len - got, 0);
    if (n <= 0) return -1;
    got += (size_t)n;
  }
  return 0;
}

static int send_all(int fd, const uint8_t *buf, size_t len) {
  while (len) {
    ssize_t n = send(fd, buf, len, MSG_NOSIGNAL);
    if (n <= 0) return -1;
    buf += n;
    len -= (size_t)n;
  }
  return 0;
}

static int handshake(int fd) {
  uint32_t req[3];
  if (recv_exact(fd, (uint8_t *)req, sizeof(req))) return -1;
  if (ntohl(req[0]) != EL_LINK_IDENTIFIER || ntohl(req[1]) != EL_COMMAND_HANDSHAKE) {
    fprintf(stderr, "not an elaphureLink client, closing\n");
    return -1;
  }
  uint32_t res[3] = {htonl(EL_LINK_IDENTIFIER), htonl(EL_COMMAND_HANDSHAKE), htonl(EL_DAP_VERSION)};
  return send_all(fd, (const uint8_t *)res, sizeof(res));
}

static void serve(int fd) {
  static uint8_t req[DAP_PACKET_SIZE * 2];
  static uint8_t resp[DAP_PACKET_SIZE];
  for (;;) {
    ssize_t n = recv(fd, req, sizeof(req), 0);
    if (n <= 0) return;
    // Normally one command per message; walk the buffer in case several coalesced.
    size_t off = 0;
    while (off < (size_t)n) {
      memset(resp, 0, sizeof(resp));
      uint32_t r = DAP_ExecuteCommand(req + off, resp);
      size_t req_len = r >> 16;
      size_t resp_len = r & 0xffffu;
      if (send_all(fd, resp, resp_len)) return;
      if (req_len == 0) break;
      off += req_len;
    }
  }
}

static void usage(const char *argv0) {
  fprintf(stderr,
          "usage: %s [--port 3240] [--swclk 25] [--swdio 24] [--nreset GPIO]\n"
          "Serve a CMSIS-DAP SWD probe over elaphureLink, bit-banging Pi 5 header GPIOs.\n",
          argv0);
}

int main(int argc, char **argv) {
  int port = 3240, swclk = 25, swdio = 24, nreset = -1;
  static const struct option opts[] = {{"port", required_argument, 0, 'p'},
                                       {"swclk", required_argument, 0, 'c'},
                                       {"swdio", required_argument, 0, 'd'},
                                       {"nreset", required_argument, 0, 'r'},
                                       {"help", no_argument, 0, 'h'},
                                       {0, 0, 0, 0}};
  int opt;
  while ((opt = getopt_long(argc, argv, "p:c:d:r:h", opts, NULL)) != -1) {
    switch (opt) {
      case 'p': port = atoi(optarg); break;
      case 'c': swclk = atoi(optarg); break;
      case 'd': swdio = atoi(optarg); break;
      case 'r': nreset = atoi(optarg); break;
      default: usage(argv[0]); return opt == 'h' ? 0 : 2;
    }
  }
  if (swclk < 0 || swclk > 27 || swdio < 0 || swdio > 27 || swclk == swdio || nreset > 27) {
    fprintf(stderr, "pins must be distinct header GPIOs 0-27\n");
    return 2;
  }

  if (gethostname(swd_serial, sizeof(swd_serial) - 1)) strcpy(swd_serial, "rpi5");
  if (rp1_open()) return 1;

  signal(SIGINT, on_signal);
  signal(SIGTERM, on_signal);
  rp1_claim((unsigned)swclk, 0);
  rp1_claim((unsigned)swdio, RP1_PAD_PUE);
  swd_clk_mask = 1u << swclk;
  swd_dio_mask = 1u << swdio;
  if (nreset >= 0) {
    rp1_claim((unsigned)nreset, RP1_PAD_PUE);
    swd_nreset_mask = 1u << nreset;
  }
  DAP_Setup();

  int ls = socket(AF_INET6, SOCK_STREAM, 0);
  int on = 1, off = 0;
  setsockopt(ls, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
  setsockopt(ls, IPPROTO_IPV6, IPV6_V6ONLY, &off, sizeof(off));
  struct sockaddr_in6 addr = {.sin6_family = AF_INET6, .sin6_port = htons((uint16_t)port),
                              .sin6_addr = in6addr_any};
  if (bind(ls, (struct sockaddr *)&addr, sizeof(addr)) || listen(ls, 1)) {
    perror("bind/listen");
    rp1_restore_all();
    return 1;
  }
  fprintf(stderr, "swd_bridge: SWCLK=GPIO%d SWDIO=GPIO%d nRESET=%s, elaphureLink on :%d\n", swclk,
          swdio, nreset >= 0 ? "GPIO" : "none", port);
  if (nreset >= 0) fprintf(stderr, "  nRESET on GPIO%d\n", nreset);

  for (;;) {
    int fd = accept(ls, NULL, NULL);
    if (fd < 0) {
      if (errno == EINTR) continue;
      perror("accept");
      break;
    }
    setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &on, sizeof(on));
    if (handshake(fd) == 0) {
      fprintf(stderr, "client connected\n");
      serve(fd);
      fprintf(stderr, "client disconnected\n");
    }
    close(fd);
    PORT_OFF();  // release the target between sessions
  }
  rp1_restore_all();
  return 0;
}

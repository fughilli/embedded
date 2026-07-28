// On-device self-signed certificate (re)issuance for the player's wss endpoint.
//
// The build-time dev cert (devcert/) carries no subjectAltName, so modern
// browsers reject it (fatal alert -> the phone can't take the trust exception).
// This re-issues a cert for an EXISTING private key with the device's live IPs
// in the SAN, so the cert-approval page loads. Reusing the build-time key avoids
// slow on-device RSA keygen; a fixed serial/validity makes the output
// byte-identical across reboots for the same key+SAN, so the browser's stored
// exception survives reboots (only an IP/SAN change re-issues a new cert).
//
// Plain C API (no mbedtls types) so callers don't need the (pruned) mbedtls
// x509-writer headers — this TU is compiled against the ledmapper mbedtls config
// that enables them.
#ifndef LEDMAPPER_LIBS_TLS_SELFSIGNED_H_
#define LEDMAPPER_LIBS_TLS_SELFSIGNED_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Re-issue a self-signed cert for `key_pem` (a PEM private key, NUL-terminated),
// with subject/issuer CN=`cn` and a SAN of `n_ips` IPv4 addresses (each a 4-byte
// octet sequence a.b.c.d packed into a uint32 in memory order — an Arduino
// IPAddress or esp_ip4_addr_t `.addr` value works directly) plus optional DNS
// name `dns` (may be NULL). Writes a NUL-terminated PEM cert to `out_pem`.
// Returns 0 on success, or a negative mbedtls error code.
int ledmapper_selfsign(const char *key_pem, const char *cn,
                       const uint32_t *ipv4, int n_ips, const char *dns,
                       char *out_pem, size_t out_cap);

#ifdef __cplusplus
}  // extern "C"
#endif

#endif  // LEDMAPPER_LIBS_TLS_SELFSIGNED_H_

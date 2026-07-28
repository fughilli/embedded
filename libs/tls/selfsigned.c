#include "selfsigned.h"

#include <string.h>

#include "mbedtls/ctr_drbg.h"
#include "mbedtls/entropy.h"
#include "mbedtls/pk.h"
#include "mbedtls/x509_crt.h"

#define MAX_IPS 4

int ledmapper_selfsign(const char *key_pem, const char *cn,
                       const uint32_t *ipv4, int n_ips, const char *dns,
                       char *out_pem, size_t out_cap) {
    int ret;
    mbedtls_pk_context key;
    mbedtls_x509write_cert crt;
    mbedtls_ctr_drbg_context drbg;
    mbedtls_entropy_context entropy;

    mbedtls_pk_init(&key);
    mbedtls_x509write_crt_init(&crt);
    mbedtls_ctr_drbg_init(&drbg);
    mbedtls_entropy_init(&entropy);

    const char *pers = "ledmapper-selfsign";
    if ((ret = mbedtls_ctr_drbg_seed(&drbg, mbedtls_entropy_func, &entropy,
                                     (const unsigned char *)pers, strlen(pers))) != 0)
        goto done;

    // Reuse the build-time key (PEM incl. trailing NUL in the length).
    if ((ret = mbedtls_pk_parse_key(&key, (const unsigned char *)key_pem,
                                    strlen(key_pem) + 1, NULL, 0,
                                    mbedtls_ctr_drbg_random, &drbg)) != 0)
        goto done;

    char dn[96];
    snprintf(dn, sizeof dn, "CN=%s", (cn && cn[0]) ? cn : "ledmapper-player");

    mbedtls_x509write_crt_set_version(&crt, MBEDTLS_X509_CRT_VERSION_3);
    mbedtls_x509write_crt_set_md_alg(&crt, MBEDTLS_MD_SHA256);
    mbedtls_x509write_crt_set_subject_key(&crt, &key);
    mbedtls_x509write_crt_set_issuer_key(&crt, &key);
    if ((ret = mbedtls_x509write_crt_set_subject_name(&crt, dn)) != 0) goto done;
    if ((ret = mbedtls_x509write_crt_set_issuer_name(&crt, dn)) != 0) goto done;

    // Fixed serial + validity => deterministic bytes across reboots (browser
    // trust exception sticks). The device has no RTC; a wide past..future window
    // is validated against the BROWSER's clock, which is correct.
    {
        const unsigned char serial[] = {0x01};
        if ((ret = mbedtls_x509write_crt_set_serial_raw(&crt, (unsigned char *)serial,
                                                        sizeof serial)) != 0)
            goto done;
    }
    if ((ret = mbedtls_x509write_crt_set_validity(&crt, "20240101000000",
                                                  "20340101000000")) != 0)
        goto done;
    if ((ret = mbedtls_x509write_crt_set_basic_constraints(&crt, 0, -1)) != 0) goto done;

    // SAN: IP addresses (4 raw octets each) + optional DNS name, as a linked list.
    {
        mbedtls_x509_san_list sans[MAX_IPS + 1];
        unsigned char ipbuf[MAX_IPS][4];
        memset(sans, 0, sizeof sans);
        int n = 0;
        for (int i = 0; i < n_ips && i < MAX_IPS; i++) {
            memcpy(ipbuf[i], &ipv4[i], 4);  // memory order a.b.c.d == SAN bytes
            sans[n].node.type = MBEDTLS_X509_SAN_IP_ADDRESS;
            sans[n].node.san.unstructured_name.p = ipbuf[i];
            sans[n].node.san.unstructured_name.len = 4;
            sans[n].next = NULL;
            if (n > 0) sans[n - 1].next = &sans[n];
            n++;
        }
        if (dns && dns[0]) {
            sans[n].node.type = MBEDTLS_X509_SAN_DNS_NAME;
            sans[n].node.san.unstructured_name.p = (unsigned char *)dns;
            sans[n].node.san.unstructured_name.len = strlen(dns);
            sans[n].next = NULL;
            if (n > 0) sans[n - 1].next = &sans[n];
            n++;
        }
        if (n > 0 &&
            (ret = mbedtls_x509write_crt_set_subject_alternative_name(&crt, &sans[0])) != 0)
            goto done;
    }

    ret = mbedtls_x509write_crt_pem(&crt, (unsigned char *)out_pem, out_cap,
                                    mbedtls_ctr_drbg_random, &drbg);

done:
    mbedtls_x509write_crt_free(&crt);
    mbedtls_pk_free(&key);
    mbedtls_ctr_drbg_free(&drbg);
    mbedtls_entropy_free(&entropy);
    return ret;
}

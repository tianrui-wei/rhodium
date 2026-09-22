/* Measures identical mixed Queue stimuli and checks pre/post-edge outputs against an independent oracle. */
// SPDX-License-Identifier: Apache-2.0
#define _POSIX_C_SOURCE 200809L
#include "../runtime/include/rhodium_sim.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static void check(rds_sim *s, int status) {
    if (status) { fprintf(stderr, "%s\n", rds_error(s)); exit(1); }
}
static double now(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec * 1e-9;
}
static uint64_t random_word(uint64_t *state) {
    *state ^= *state << 13; *state ^= *state >> 7; *state ^= *state << 17;
    return *state;
}
int main(int argc, char **argv) {
    if (argc != 7) return 2;
    char error[512];
    rds_options options = {1, 0};
    rds_sim *s = rds_load_with_options(argv[1], &options, error, sizeof error);
    if (!s) { fprintf(stderr, "%s\n", error); return 1; }
    if (!strcmp(argv[2], "emit")) {
        check(s, rds_emit_c(s, argv[3], 0)); rds_free(s); return 0;
    }
    if (strcmp(argv[3], "-")) check(s, rds_use_compiled(s, argv[3]));
    unsigned depth = (unsigned)strtoul(argv[4], NULL, 10);
    int bypass = atoi(argv[5]);
    uint64_t cycles = strtoull(argv[6], NULL, 10);
    if (!depth || depth > 1024 || !cycles) return 2;
    const char *inputs[] = {"payload", "valid", "ready", "enable", "reset"};
    const char *outputs[] = {"input_ready", "output_valid", "output_payload", "occupancy", "phase"};
    int in[5], out[5];
    for (unsigned i = 0; i < 5; ++i) {
        in[i] = rds_find_port(s, inputs[i]); out[i] = rds_find_port(s, outputs[i]);
        if (in[i] < 0 || out[i] < 0) return 2;
    }
    unsigned char storage[1024] = {0};
    unsigned read = 0, write = 0, count = 0, phase = 0;
    uint64_t rng = UINT64_C(12648430), digest = 0;
    double start = now();
    for (uint64_t cycle = 0; cycle < cycles; ++cycle) {
        uint64_t values[] = {random_word(&rng) & 255, random_word(&rng) % 4 != 0,
                            random_word(&rng) % 3 != 0, random_word(&rng) % 5 != 0,
                            cycle < 2 || cycle % 503 == 0};
        for (unsigned i = 0; i < 5; ++i) check(s, rds_set_u64(s, in[i], values[i]));
        for (unsigned edge = 0; edge < 2; ++edge) {
            check(s, rds_eval(s));
            unsigned valid = values[1] && values[3], ready = count < depth || (bypass && values[2]);
            unsigned payload = bypass && !count ? (values[0] + phase) & 255 : storage[read];
            uint64_t expected[] = {ready && values[3], count > 0 || (bypass && valid), payload ^ phase, count, phase};
            for (unsigned i = 0; i < 5; ++i) {
                uint64_t actual; check(s, rds_get_u64(s, out[i], &actual));
                if (actual != expected[i]) {
                    fprintf(stderr, "cycle=%" PRIu64 " edge=%u port=%s actual=%" PRIu64 " expected=%" PRIu64 "\n", cycle, edge, outputs[i], actual, expected[i]);
                    return 1;
                }
                digest = (digest ^ actual) * UINT64_C(1099511628211);
            }
            if (!edge) {
                int enqueue = valid && ready, dequeue = values[2] && (count > 0 || (bypass && valid));
                if (bypass && !count) { if (values[2]) enqueue = 0; dequeue = 0; }
                if (enqueue) storage[write] = (unsigned char)(values[0] + phase);
                if (values[4]) { count = read = write = 0; phase = 1; }
                else { count += enqueue - dequeue; read = (read + dequeue) % depth; write = (write + enqueue) % depth; phase = (phase + 1) & 255; }
                check(s, rds_advance(s));
            }
        }
    }
    printf("%.9f %" PRIu64 "\n", now() - start, digest);
    rds_free(s); return 0;
}

// Replays Queue/pipe stimuli and reports every public output before and after clock edges.
// SPDX-License-Identifier: Apache-2.0
#include "VMixedPipe.h"
#include "verilated.h"
#include <iostream>

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    VMixedPipe top;
    unsigned payload, valid, ready, flush, reset;
    auto sample = [&]() {
        std::cout << unsigned(top.input_ready) << ' ' << unsigned(top.output_valid) << ' '
                  << unsigned(top.output_payload) << ' ' << unsigned(top.occupancy) << '\n';
    };
    while (std::cin >> payload >> valid >> ready >> flush >> reset) {
        top.clock = 0;
        top.payload = payload;
        top.valid = valid;
        top.ready = ready;
        top.flush = flush;
        top.reset = reset;
        top.eval();
        sample();
        top.clock = 1;
        top.eval();
        sample();
        top.clock = 0;
        top.eval();
    }
    top.final();
}

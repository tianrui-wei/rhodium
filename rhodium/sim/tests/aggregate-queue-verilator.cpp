// Replays aggregate Queue feedback inputs against independently lowered SystemVerilog.
// SPDX-License-Identifier: Apache-2.0
#include "VAggregateQueue.h"
#include "verilated.h"
#include <iostream>

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    VAggregateQueue top;
    unsigned payload, valid, ready, reset;
    auto sample = [&]() {
        std::cout << unsigned(top.input_ready) << ' ' << unsigned(top.output_valid) << ' '
                  << unsigned(top.left) << ' ' << unsigned(top.right) << ' '
                  << unsigned(top.occupancy) << '\n';
    };
    while (std::cin >> payload >> valid >> ready >> reset) {
        top.clock = 0;
        top.payload = payload;
        top.valid = valid;
        top.ready = ready;
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

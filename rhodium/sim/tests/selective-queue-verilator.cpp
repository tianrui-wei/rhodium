// Replays the same public input vectors against CIRCT-emitted SystemVerilog before and after each edge.
// SPDX-License-Identifier: Apache-2.0
#include "VMixedSelective.h"
#include "verilated.h"
#include <iostream>

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    VMixedSelective top;
    unsigned payload, valid, ready, enable, reset;
    auto sample = [&]() {
        std::cout << unsigned(top.input_ready) << ' ' << unsigned(top.output_valid) << ' '
                  << unsigned(top.output_payload) << ' ' << unsigned(top.occupancy) << ' '
                  << unsigned(top.phase) << '\n';
    };
    while (std::cin >> payload >> valid >> ready >> enable >> reset) {
        top.clock = 0;
        top.payload = payload;
        top.valid = valid;
        top.ready = ready;
        top.enable = enable;
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

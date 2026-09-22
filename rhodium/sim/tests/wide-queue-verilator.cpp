// Replays multiword Queue feedback inputs against independently lowered SystemVerilog.
// SPDX-License-Identifier: Apache-2.0
#include "VAggregateQueue.h"
#include "verilated.h"
#include <iostream>
#include <cstdint>

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    VAggregateQueue top;
    std::uint64_t payload;
    unsigned payload_high, valid, ready, reset;
    auto sample = [&]() {
        std::cout << unsigned(top.input_ready) << ' ' << unsigned(top.output_valid) << ' '
                  << std::uint64_t(top.left) << ' ' << std::uint64_t(top.right) << ' '
                  << unsigned(top.occupancy) << ' ' << unsigned(top.left_high) << ' '
                  << unsigned(top.right_high) << '\n';
    };
    while (std::cin >> payload >> payload_high >> valid >> ready >> reset) {
        top.clock = 0;
        top.payload = payload;
        top.payload_high = payload_high;
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

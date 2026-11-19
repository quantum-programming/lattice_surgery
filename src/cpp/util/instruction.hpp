#pragma once

#include <algorithm>
#include <cassert>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "constants.hpp"

struct Instruction {
  int instId;
  std::string gate;

  // targetIds: which logical qubits are involved
  //            if the id==-1, it means we will use the magic state factory.
  //            However, notice that we should connect to an idx larger than
  //            or equal to prob.data_qubits.size().
  std::vector<int> targetIds;

  std::vector<std::vector<Direction>> directions;
  // Used by the two-endpoint path checks.
  std::array<bool, 2> kink_parity_allowed{};

  Instruction(const std::string& gate, int control, int target, int instId)
      : Instruction(gate,
                    gate == "CX" ? std::vector<int>{control, target}
                                 : std::vector<int>{target},
                    instId) {}

  Instruction(const std::string& gate, std::vector<int> operands, int instId)
      : instId(instId), gate(gate), targetIds(std::move(operands)) {
    if (gate == "CX") {
      directions = {{Direction::H}, {Direction::V}};
      kink_parity_allowed = {false, true};
    } else if (gate == "MAGIC_MZZ") {
      directions = {{Direction::H}, {Direction::H}};
      kink_parity_allowed = {true, false};
    } else if (gate == "MAGIC_MOVE") {
      directions = {{Direction::H, Direction::V}, {Direction::H, Direction::V}};
      kink_parity_allowed = {true, true};
    } else if (gate == "MAGIC_MZ3" || gate == "MAGIC_MZ4") {
      directions.assign(gate == "MAGIC_MZ3" ? 3 : 4, {Direction::H});
    } else {
      throw std::runtime_error("Unknown gate: " + gate);
    }

    if (gate != "CX") targetIds.insert(targetIds.begin(), -1);
    assert(targetIds.size() == directions.size());
  }

  friend std::ostream& operator<<(std::ostream& os, const Instruction& inst) {
    int t = inst.targetIds.size();
    os << t << '\n';
    for (int i = 0; i < t; i++) os << inst.targetIds[i] << ' ';
    os << '\n';
    return os;
  }
};

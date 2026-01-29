#pragma once

#include <queue>
#include <set>

#include "instruction.hpp"

struct InstructionDependencyManager : std::set<int> {
  enum State { Ready, Unready, Finished };

  int data_count;
  std::vector<std::queue<int>> queues;
  int finish_count = 0;

  std::vector<Instruction> instructions;
  std::vector<int> in_degrees;
  std::vector<State> states;

  InstructionDependencyManager(int data_count,
                               const std::vector<Instruction>& instructions)
      : data_count(data_count), queues(data_count) {
    this->instructions.reserve(instructions.size());
    in_degrees.reserve(instructions.size());
    states.reserve(instructions.size());
    for (auto&& inst : instructions) {
      push_back_instruction(inst);
    }
  }

  void push_back_instruction(const Instruction& inst) {
    int inst_index = instructions.size();

    instructions.push_back(inst);
    in_degrees.push_back(0);
    states.push_back(Unready);

    for (const auto& target_id : inst.targetIds) {
      if (target_id == -1) continue;
      auto&& q = queues[target_id];
      in_degrees[inst_index] += int(!q.empty());
      q.push(inst_index);
    }

    if (in_degrees[inst_index] == 0) {
      states[inst_index] = Ready;
      insert(inst_index);
    }
  }

  // Returns an iterator that follows the erased instruction.
  std::set<int>::iterator process_instruction(int inst_index) {
    assert(0 <= inst_index && inst_index < int(instructions.size()));
    assert(states[inst_index] == Ready);

    finish_count++;
    states[inst_index] = Finished;
    Instruction inst = instructions[inst_index];
    for (const auto& target_id : inst.targetIds) {
      if (target_id == -1) continue;
      auto&& q = queues[target_id];
      assert(q.front() == inst_index);
      q.pop();
      if (!q.empty()) {
        int next_inst_index = q.front();
        in_degrees[next_inst_index] -= 1;
        if (in_degrees[next_inst_index] == 0) {
          states[next_inst_index] = Ready;
          insert(next_inst_index);
        }
      }
    }
    return erase(find(inst_index));
  }

  Instruction get_instruction(int inst_index) {
    assert(0 <= inst_index && inst_index < int(instructions.size()));
    return instructions[inst_index];
  }

  State get_state(int inst_index) {
    assert(0 <= inst_index && inst_index < int(instructions.size()));
    return states[inst_index];
  }

  bool all_finished() { return finish_count == int(instructions.size()); }

  std::set<int> get_ready_indices() { return *this; }
};

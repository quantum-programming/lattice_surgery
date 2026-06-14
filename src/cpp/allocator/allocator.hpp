#pragma once

#include <algorithm>
#include <cassert>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>
#include <tuple>
#include <vector>

#include "../util/problem.hpp"
#include "sa_solver.hpp"

class Allocator {
 public:
  Allocator() : engine(1) {}

  /**
   * @brief Allocate data qubits to the chip.
   * @param prob The problem instance to be updated.
   * @param factory_method "outer" or "inner"(magic cultivation).
   * @param allocation_method  "random", "SA" or "naive".
   * @param layer_count The number of layers.
   * @param msf_coeff For SA. The coefficient for the magic state factory.
   * @param iters For SA. The number of iterations.
   */
  void allocate(Problem& prob, std::string factory_method,
                std::string allocation_method, int layer_count,
                double msf_coeff, int iters) {
    assert(layer_count == 1 || layer_count == 2);
    engine.seed(1);  // For reproducibility.
    prob.reset();
    prob.layer_count = layer_count;
    this->factory_method = factory_method;
    this->msf_coeff = msf_coeff;
    this->iters = iters;

    std::vector<Pos> alloc, factory;
    if (allocation_method == "naive")
      tie(prob.width, prob.height, alloc, factory) = naive_alloc(prob);
    else if (allocation_method == "random")
      tie(prob.width, prob.height, alloc, factory) = random_alloc(prob);
    else if (allocation_method == "SA")
      tie(prob.width, prob.height, alloc, factory) = SA_alloc(prob);
    else
      throw std::invalid_argument("Unknown method: " + allocation_method);

    // Update problem.
    assert(prob.data_qubits.size() == alloc.size());
    assert(prob.ms_factories.empty());
    assert(prob.position2qubit_index.empty());
    prob.chip_size = prob.width * prob.height * prob.layer_count;
    for (int i = 0; i < int(alloc.size()); i++) {
      int position = prob.xyz_to_position(alloc[i]);
      prob.data_qubits[i] = position;
      prob.position2qubit_index[position] = i;
    }
    for (int i = 0; i < int(factory.size()); i++) {
      int position = prob.xyz_to_position(factory[i]);
      prob.ms_factories.push_back(position);
      prob.position2qubit_index[position] = prob.data_qubits.size() + i;
    }
    // Different qubits occupy different positions.
    assert(prob.position2qubit_index.size() == alloc.size() + factory.size());
  }

 private:
  using Pos = std::tuple<int, int, int>;
  using Result = std::tuple<int, int, std::vector<Pos>, std::vector<Pos>>;

  // Parameters
  double msf_coeff;
  int iters;
  std::mt19937 engine;
  std::string factory_method;

  Result _base_for_allocation(const Problem& prob) {
    //
    // #.#.#.#  .: logical qubit
    // .......  #: magic state factory
    // #.@.@.#  @: data qubit
    // .......  E: empty position
    // #.@.E.#
    // .......  (sz-1)^2 < #data qubits <= sz^2
    // #.#.#.#  w=sz*2+3, h=sz*2+3
    //
    assert(prob.layer_count == 1 || prob.layer_count == 2);
    int sz_2d = 0, sz_25d = 0;
    while (sz_2d * sz_2d < int(prob.data_qubits.size())) sz_2d++;
    while (sz_25d * sz_25d * 2 < int(prob.data_qubits.size())) sz_25d++;
    int sz;
    if (prob.layer_count == 1)
      sz = sz_2d;
    else if (prob.layer_count == 2)
      sz = sz_25d;
    else
      throw std::invalid_argument("Invalid layer count.");
    int w = sz * 2 + 3, h = sz * 2 + 3;
    std::vector<Pos> alloc, factory;
    for (int i = 0; i < sz; i++)
      for (int j = 0; j < sz; j++)
        for (int l = 0; l < prob.layer_count; l++)
          alloc.emplace_back(2 + i * 2, 2 + j * 2, l);
    for (int i = 0; i < w; i++)
      for (int j = 0; j < h; j++)
        if ((i == 0 || i == w - 1 || j == 0 || j == h - 1) && (i + j) % 2 == 0)
          for (int l = 0; l < prob.layer_count; l++)
            factory.emplace_back(i, j, l);
    assert(int(factory.size()) == 4 * (sz + 1) * prob.layer_count);

    if (prob.layer_count == 2) {
      // only use the same number of msf as the 2d case
      while (int(factory.size()) > 4 * (sz_2d + 1)) {
        if (factory_method == "inner") alloc.push_back(factory.back());
        factory.pop_back();
      }
    }

    assert(int(factory.size()) == 4 * (sz_2d + 1));
    return {w, h, alloc, factory};
  }

  Result naive_alloc(const Problem& prob) {
    auto [w, h, alloc, factory] = _base_for_allocation(prob);
    if (factory_method == "inner") {
      std::vector<Pos> loc(alloc.begin(), alloc.end());
      loc.insert(loc.end(), factory.begin(), factory.end());
      std::sort(loc.begin(), loc.end());
      alloc.assign(loc.begin(), loc.begin() + prob.data_qubits.size());
      factory.assign(loc.begin() + prob.data_qubits.size(),
                     loc.begin() + prob.data_qubits.size() + factory.size());
    } else if (factory_method == "outer") {
      alloc.resize(prob.data_qubits.size());
    }
    return {w, h, alloc, factory};
  }

  Result random_alloc(const Problem& prob) {
    auto [w, h, alloc, factory] = _base_for_allocation(prob);
    if (factory_method == "inner") {
      std::vector<Pos> loc(alloc.begin(), alloc.end());
      loc.insert(loc.end(), factory.begin(), factory.end());
      std::shuffle(loc.begin(), loc.end(), engine);
      alloc.assign(loc.begin(), loc.begin() + prob.data_qubits.size());
      factory.assign(loc.begin() + prob.data_qubits.size(),
                     loc.begin() + prob.data_qubits.size() + factory.size());
    } else if (factory_method == "outer") {
      std::shuffle(alloc.begin(), alloc.end(), engine);
      alloc.resize(prob.data_qubits.size());
    }
    return {w, h, alloc, factory};
  }

  Result SA_alloc(Problem& prob) {
    auto [w, h, alloc, factory] = _base_for_allocation(prob);
    prob.width = w, prob.height = h;
    prob.chip_size = w * h * prob.layer_count;
    assert(prob.position2qubit_index.empty());
    SASolver solver(prob, msf_coeff, iters);
    solver.SA(prob, alloc, factory, factory_method == "outer");
    return {w, h, alloc, factory};
  }

  // bool is_in_dense(int h, int w) {
  //   if (h == 0 || w == 0) return false;
  //   h = (h - 1) % 4, w = (w - 1) % 4;
  //   std::string pattern =  // Repeat this 4x4 pattern. 50% area is used.
  //       "##.."
  //       ".##."
  //       "..##"
  //       "#..#";
  //   return pattern[h * 4 + w] == '#';
  // }
};

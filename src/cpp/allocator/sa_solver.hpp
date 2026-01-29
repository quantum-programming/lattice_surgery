#pragma once
#include <algorithm>
#include <cassert>
#include <cmath>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <stdexcept>
#include <tuple>
#include <vector>

#include "../util/problem.hpp"

using Pos = std::tuple<int, int, int>;
using Heatmap = std::vector<std::vector<std::pair<int, int>>>;

/**
 * @brief Heatmap for the qubit allocation.
 *  Let n be the number of data qubits.
 *  The n-th qubit represents the magic state factories (MSF).
 *  The heatmap is a 2D array of size (n+1) x (n+1), satisfying:
 *  - heatmap[i][j] = (# of instructions between qubit i and qubit j)
 *  - heatmap[i][n] = (# of instructions between qubit i and the MSF)
 */
Heatmap createHeatmap(const Problem& prob) {
  assert(prob.data_qubits.size() > 0);
  std::map<int, std::map<int, int>> _heatmap;
  for (auto& inst : prob.instructions)
    for (auto target : inst.targetIds)
      for (auto target2 : inst.targetIds) {
        if (target >= target2) continue;
        assert(-1 <= target && target < int(prob.data_qubits.size()));
        _heatmap[target][target2]++;
        _heatmap[target2][target]++;
      }
  Heatmap data(prob.data_qubits.size() + 1);
  for (auto [_i, row] : _heatmap) {
    int i = _i == -1 ? prob.data_qubits.size() : _i;
    for (auto [j, heat] : row) {
      if (j == -1) continue;
      data[i].emplace_back(j, heat);
    }
    if (row.count(-1))
      data[i].emplace_back(prob.data_qubits.size(), row.at(-1));
  }
  return data;
}

class SASolver {
  /**
   * @brief Simulated Annealing (SA) solver for qubit allocation.
   * @note There are n data qubits and some of magic state factories,
   *       which location is fixed. Our goal is to allocate the data qubits.
   *       We define the objective function for the SA solver as:
   *       f(Q) = \sum_{q1<q2} heatmap[q1][q2] * dist(q1,q2)
   *             + \sum_{q} heatmap[q][n] * dist_to_msf(q)
   *       where Q={q_0,q_1,...q_{n-1}} is the qubit allocation and
   *       n represents the magic state factory (msf).
   */

 public:
  SASolver(const Problem& prob, double msf_coeff, int iters)
      : MSF_COEFF(msf_coeff), ITERS(iters) {
    assert(MSF_COEFF >= 0.0);
    assert(ITERS > 0);
    chip_adj = prob.make_adj_ancillary();
  }

  /**
   * @brief SA solver for qubit allocation.
   * @param prob The problem instance to be updated.
   * @param alloc The default qubit allocation.
   * @param factory The default locations of the msf.
   * @param is_outer Whether the locations of msf are fixed.
   * @return void, but the allocation is updated in-place.
   */
  void SA(const Problem& prob, std::vector<Pos>& alloc,
          std::vector<Pos>& factory, const bool is_outer) {
    this->n_qubit = prob.data_qubits.size();
    this->n_msf = factory.size();
    assert(int(alloc.size()) >= n_qubit);  // contains surplus candidates
    std::mt19937 mt(1);

    std::vector<Pos> locations;
    locations.reserve(alloc.size() + factory.size());
    for (auto& loc : alloc) locations.push_back(loc);
    for (auto& loc : factory) locations.push_back(loc);
    int maxLId = is_outer ? alloc.size() : locations.size();

    // loc2id: loc2id[location_index] = qid (qid indicates the data)
    // id2loc: id2loc[qid] = location_index (qubit or msf)
    std::vector<int> loc2id(locations.size(), -1);
    std::vector<int> id2loc(n_qubit + n_msf, -1);
    std::vector<int> random_loc_ids(maxLId);
    std::iota(random_loc_ids.begin(), random_loc_ids.end(), 0);
    std::shuffle(random_loc_ids.begin(), random_loc_ids.end(), mt);
    for (int qid = 0; qid < n_qubit; qid++) {
      int loc_id = random_loc_ids.back();
      random_loc_ids.pop_back();
      loc2id[loc_id] = qid;
      id2loc[qid] = loc_id;
    }
    for (int msf = 0; msf < n_msf; msf++) {
      int loc_id = int(locations.size()) - 1 - msf;
      if (!is_outer) {
        loc_id = random_loc_ids.back();
        random_loc_ids.pop_back();
      }
      loc2id[loc_id] = n_qubit + msf;
      id2loc[n_qubit + msf] = loc_id;
    }

    // [0,n): data qubits to be allocated.
    //    n : represents the magic state factory.
    Heatmap heatmap = createHeatmap(prob);
    assert(int(heatmap.size()) == n_qubit + 1);
    update_dist_table(prob, locations, id2loc);

    // Compute the initial score.
    double bestScore = compute_score(heatmap, locations, id2loc);
    double T0 = 10000, T1 = 0.1;
    for (int iter = 0; iter < ITERS; iter++) {
      const int loc1 = mt() % maxLId, loc2 = mt() % maxLId;
      if (loc1 == loc2) continue;
      const int q1 = loc2id[loc1], q2 = loc2id[loc2];
      assert(q1 == -1 || id2loc[q1] == loc1);
      assert(q2 == -1 || id2loc[q2] == loc2);
      if (q1 == -1 && q2 == -1) continue;            // both are empty locations
      if (q1 >= n_qubit && q2 >= n_qubit) continue;  // both are msf
      assert(q1 != q2);

      double scoreDelta =
          do_swap(prob, heatmap, locations, loc2id, id2loc, q1, q2, loc1, loc2);

      double temperature = T0 + (T1 - T0) * iter / ITERS;
      if (scoreDelta < 0 ||
          std::exp(-scoreDelta / temperature) > mt() / double(mt.max())) {
        bestScore += scoreDelta;
      } else {
        std::swap(loc2id[loc1], loc2id[loc2]);
        if (q1 != -1) id2loc[q1] = loc1;
        if (q2 != -1) id2loc[q2] = loc2;
        if (q1 >= n_qubit || q2 >= n_qubit)
          std::swap(old_dist_table, dist_table);
      }
    }
    double finalScore = compute_score(heatmap, locations, id2loc);
    assert(std::abs(finalScore - bestScore) < 1e-6);

    // Update the allocation.
    for (int i = 0; i < n_qubit; i++) {
      int loc_id = id2loc[i];
      assert(loc_id != -1);
      alloc[i] = locations[loc_id];
    }
    alloc.resize(n_qubit);
    for (int i = 0; i < n_msf; i++) {
      int loc_id = id2loc[n_qubit + i];
      assert(loc_id != -1);
      factory[i] = locations[loc_id];
    }
    assert(int(factory.size()) == n_msf);
  }

 private:
  int n_qubit;       // number of data qubits
  int n_msf;         // number of magic state factories
  double MSF_COEFF;  // coefficient in the objective function
  int ITERS;         // number of iterations for SA
  std::vector<int> dist_table, old_dist_table;
  std::vector<std::vector<int>> chip_adj;  // cached chip graph

  int dist_loc2(const Pos& loc1, const Pos& loc2) {
    auto [x1, y1, z1] = loc1;
    auto [x2, y2, z2] = loc2;
    return std::abs(x1 - x2) + std::abs(y1 - y2) + std::abs(z1 - z2);
  }

  void update_dist_table(const Problem& prob, const std::vector<Pos>& locations,
                         const std::vector<int>& id2loc) {
    std::vector<int> d(prob.chip_size, std::numeric_limits<int>::max());
    std::queue<int> q;
    // Multi-source: msf vertices from id2loc[n_qubit] ..
    // id2loc[n_qubit+n_msf-1]
    for (int msf = n_qubit; msf < n_qubit + n_msf; msf++) {
      int loc_idx = id2loc[msf];
      assert(loc_idx != -1);
      int chip_idx = prob.xyz_to_position(locations[loc_idx]);
      d[chip_idx] = 0;
      q.push(chip_idx);
    }
    while (!q.empty()) {
      int cur = q.front();
      q.pop();
      for (int neigh : chip_adj[cur]) {
        if (d[neigh] > d[cur] + 1) {
          d[neigh] = d[cur] + 1;
          q.push(neigh);
        }
      }
    }
    dist_table.resize(locations.size());
    for (int i = 0; i < int(locations.size()); i++) {
      int chip_idx = prob.xyz_to_position(locations[i]);
      dist_table[i] = d[chip_idx];
    }

    // for (int i = 0; i < int(locations.size()); i++) {
    //   int check = std::numeric_limits<int>::max();
    //   for (int j = n_qubit; j < n_qubit + n_msf; j++) {
    //     int dist = dist_loc2(locations[i], locations[id2loc[j]]);
    //     if (dist < check) check = dist;
    //   }
    //   assert(check == dist_table[i]);
    // }
  }

  double compute_score(const Heatmap& heatmap,
                       const std::vector<Pos>& locations,
                       const std::vector<int>& id2loc) {
    assert(!dist_table.empty());
    double totalScore = 0.0;
    for (int q1 = 0; q1 < n_qubit; q1++) {
      for (auto [q2, heatValue] : heatmap[q1]) {
        if (q2 == n_qubit) {  // data qubit -- msf
          int loc1 = id2loc[q1];
          assert(loc1 != -1);
          double d = dist_table[loc1];
          totalScore += heatValue * MSF_COEFF * d * d;
        } else if (q1 < q2) {  // data qubit -- data qubit
          int loc1 = id2loc[q1], loc2 = id2loc[q2];
          assert(loc1 != -1 && loc2 != -1);
          double d = dist_loc2(locations[loc1], locations[loc2]);
          totalScore += heatValue * d * d;
        }
      }
    }
    return totalScore;
  }

  double compute_score_msf(const Heatmap& heatmap,
                           const std::vector<int>& id2loc) {
    double totalScore = 0.0;
    for (int q1 = 0; q1 < n_qubit; q1++) {
      auto [q2, heatValue] = heatmap[q1].back();
      if (q2 != n_qubit) continue;
      double d = dist_table[id2loc[q1]];
      totalScore += heatValue * MSF_COEFF * d * d;
    }
    return totalScore;
  }

  double do_swap(const Problem& prob, const Heatmap& heatmap,
                 const std::vector<Pos>& locations, std::vector<int>& loc2id,
                 std::vector<int>& id2loc, const int q1, const int q2,
                 const int loc1, const int loc2) {
    double scoreDelta = 0.0;
    for (bool beforeSwap : {true, false}) {  // true -> -, false -> +
      for (int i : {0, 1}) {
        int qubit = (i == 0) ? q1 : q2;
        int loc = ((i == 0) ^ !beforeSwap) ? loc1 : loc2;
        if (qubit == -1) continue;       // empty
        if (qubit >= n_qubit) continue;  // msf
        for (auto [otherQubit, heatValue] : heatmap[qubit]) {
          if (otherQubit == -1) continue;
          if (otherQubit == q1 || otherQubit == q2) continue;
          if (otherQubit < n_qubit) {
            double d = dist_loc2(locations[loc], locations[id2loc[otherQubit]]);
            scoreDelta += heatValue * d * d * (beforeSwap ? -1 : +1);
          } else if (q1 < n_qubit && q2 < n_qubit) {
            double d = dist_table[loc];
            scoreDelta +=
                heatValue * MSF_COEFF * d * d * (beforeSwap ? -1 : +1);
          }
        }
      }

      if (beforeSwap) {  // do the swap
        if (q1 >= n_qubit || q2 >= n_qubit) {
          scoreDelta -= compute_score_msf(heatmap, id2loc);
        }

        std::swap(loc2id[loc1], loc2id[loc2]);
        if (q1 != -1) id2loc[q1] = loc2;
        if (q2 != -1) id2loc[q2] = loc1;

        if (q1 >= n_qubit || q2 >= n_qubit) {
          std::swap(dist_table, old_dist_table);
          update_dist_table(prob, locations, id2loc);
          scoreDelta += compute_score_msf(heatmap, id2loc);
        }
      }
    }
    return scoreDelta;
  }
};

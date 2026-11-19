#pragma once

#include <algorithm>
#include <cassert>
#include <cstddef>
#include <limits>
#include <utility>
#include <vector>

#include "../util/constants.hpp"

struct SteinerTree {
  std::vector<int> vertices;  // Unique vertex IDs from the input graph.
  std::vector<std::pair<int, int>> edges;
  std::vector<int> selected_terminals;  // In terminal_groups order.
};

// Finds a steiner tree in O(n 3^t) time,
// where n: graph size, t: #terminals.
inline SteinerTree find_minimum_steiner_tree(
    const std::vector<std::vector<int>>& adjacency,
    const std::vector<std::vector<int>>& terminal_groups) {
  assert(!terminal_groups.empty());

  for (const auto& terminals : terminal_groups) {
    if (terminals.empty()) return {};
  }

  const int vertex_count = static_cast<int>(adjacency.size());
  const std::size_t subset_count = std::size_t{1} << terminal_groups.size();

  struct State {
    int cost = INF;
    int predecessor = -1;
    std::size_t split = 0;
  };
  // states[subset][vertex]: the minimum cost of connecting vertex to the
  // given groups. A finite state has a predecessor, a split, or is a terminal.
  std::vector<std::vector<State>> states(subset_count,
                                         std::vector<State>(vertex_count));
  for (std::size_t group = 0; group < terminal_groups.size(); ++group) {
    auto& row = states[std::size_t{1} << group];
    for (int terminal : terminal_groups[group]) {
      assert(0 <= terminal && terminal < vertex_count);
      row[terminal].cost = 0;
    }
  }

  for (std::size_t subset = 1; subset < subset_count; ++subset) {
    auto& row = states[subset];
    for (std::size_t left = (subset - 1) & subset; left != 0;
         left = (left - 1) & subset) {
      const std::size_t right = subset ^ left;
      if (left > right) continue;
      for (int vertex = 0; vertex < vertex_count; ++vertex) {
        const long long merged_cost =
            static_cast<long long>(states[left][vertex].cost) +
            states[right][vertex].cost;
        // A feasible tree uses at most vertex_count - 1 edges.
        if (merged_cost < vertex_count && merged_cost < row[vertex].cost) {
          row[vertex] = {static_cast<int>(merged_cost), -1, left};
        }
      }
    }

    // Singleton subsets start at distance zero (multi-source BFS). Other
    // subsets start with the costs of the merges at each vertex.
    std::vector<std::vector<int>> buckets(vertex_count);
    for (int vertex = 0; vertex < vertex_count; ++vertex) {
      const int cost = row[vertex].cost;
      if (cost != INF) buckets[cost].push_back(vertex);
    }
    for (int cost = 0; cost + 1 < vertex_count; ++cost) {
      for (int vertex : buckets[cost]) {
        if (row[vertex].cost != cost) continue;
        for (int neighbor : adjacency[vertex]) {
          assert(0 <= neighbor && neighbor < vertex_count);
          if (cost + 1 >= row[neighbor].cost) continue;
          row[neighbor] = {cost + 1, vertex, 0};
          buckets[cost + 1].push_back(neighbor);
        }
      }
    }
  }

  const std::size_t all_groups = subset_count - 1;
  const auto& full_row = states[all_groups];
  const auto best =
      std::min_element(full_row.begin(), full_row.end(),
                       [](const State& first, const State& second) {
                         return first.cost < second.cost;
                       });
  if (best == full_row.end() || best->cost == INF) return {};

  SteinerTree tree;
  tree.selected_terminals.assign(terminal_groups.size(), -1);
  std::vector<bool> in_tree(vertex_count);
  std::vector<std::pair<std::size_t, int>> pending{
      {all_groups, static_cast<int>(best - full_row.begin())}};
  while (!pending.empty()) {
    const auto [subset, vertex] = pending.back();
    pending.pop_back();
    if (!in_tree[vertex]) {
      in_tree[vertex] = true;
      tree.vertices.push_back(vertex);
    }

    const auto& state = states[subset][vertex];
    if (state.predecessor >= 0) {
      tree.edges.emplace_back(std::minmax(vertex, state.predecessor));
      pending.emplace_back(subset, state.predecessor);
    } else if (state.split != 0) {
      pending.emplace_back(subset ^ state.split, vertex);
      pending.emplace_back(state.split, vertex);
    } else {
      std::size_t group = 0;
      while ((std::size_t{1} << group) != subset) ++group;
      tree.selected_terminals[group] = vertex;
    }
  }

  // Repeated edges or a cycle in the reconstruction would let us remove an
  // edge, contradicting the minimum cost of the full group set.
  assert(tree.edges.size() == static_cast<std::size_t>(best->cost));
  assert(tree.edges.size() + 1 == tree.vertices.size());
  return tree;
}

#pragma once

#include <algorithm>
#include <cassert>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <queue>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#include "progress.hpp"

using namespace std;

using ll = long long;

class unreachableError {};

const int INF = 1001001001;
const ll INFll = 1e18 + 1e9;

// U D L R
const vector<int> dis = {-1, 1, 0, 0};
const vector<int> djs = {0, 0, -1, 1};

// B U D L R T
const vector<int> dis3d = {0, -1, 1, 0, 0, 0};
const vector<int> djs3d = {0, 0, 0, -1, 1, 0};
const vector<int> dts3d = {-1, 0, 0, 0, 0, 1};

enum TWO_QUBIT_MEAS { MEAS_XX = 0, MEAS_ZZ = 1 };
enum UNITE_CALLBACK_TYPE { BFS, WITHOUT_TOPOLOGY };
enum UNITE_CALLBACK_TYPE_3D {
  BFS_3D,
  DIJKSTRA_3D_BFS,
  DIJKSTRA_3D_LAYER_BASED_COST,
  DIJKSTRA_3D_LAYER_CHANGE_COST,
  DIJKSTRA_3D_LAYER_MIX_COST,
  DIJKSTRA_3D_LAYER_EXP_COST,
  WITHOUT_TOPOLOGY_3D
};
enum UNITE_CALLBACK_TYPE_PJ {
  BFS_PJ,
  DIJKSTRA_PJ_BFS,
  DIJKSTRA_PJ_LAYER_BASED_COST,
  DIJKSTRA_PJ_LAYER_EXP_COST,
};

struct two_qubit_instruction {
  TWO_QUBIT_MEAS type;
  int index_start, index_end;

  const string to_string() const {
    return string((type == MEAS_XX ? "MEAS_XX" : "MEAS_ZZ")) + " " +
           std::to_string(index_start) + " " + std::to_string(index_end);
  }

  friend ostream &operator<<(ostream &os, const two_qubit_instruction &i) {
    return os << i.to_string();
  }

  friend istream &operator>>(istream &is, two_qubit_instruction &i) {
    string type_str;
    TWO_QUBIT_MEAS type;
    int index_start, index_end;
    is >> type_str >> index_start >> index_end;
    if (type_str == "MEAS_XX") {
      type = MEAS_XX;
    } else if (type_str == "MEAS_ZZ") {
      type = MEAS_ZZ;
    } else {
      throw new unreachableError();
    }
    i = {type, index_start, index_end};
    return is;
  }
};

class qubit_plane {
 public:
  int main_qubit_size;
  int full_qubit_size;
  int main_qubit_count;
  int full_qubit_count;
  int main_qubit_count_digit;

  vector<two_qubit_instruction> instructions;

  qubit_plane(int n, unsigned seed = 0) {
    assert(n > 1);
    main_qubit_size = n;
    full_qubit_size = 2 * n + 1;
    main_qubit_count = main_qubit_size * main_qubit_size;
    full_qubit_count = full_qubit_size * full_qubit_size;
    main_qubit_count_digit = to_string(main_qubit_count).length();

    mt = mt19937(seed);
    random_main_qubit = uniform_int_distribution<int>(0, main_qubit_count - 1);
    rand2 = uniform_int_distribution<int>(0, 1);
  }

  void generate_random_instructions(int instructions_count) {
    instructions.clear();
    instructions.reserve(instructions_count);
    for (int i = 0; i < instructions_count; i++) {
      instructions.push_back(_generate_random_instruction());
      // cerr << instructions[i] << endl;
    }
  }

  void assign_instructions(const vector<two_qubit_instruction> &instructions_input) {
    instructions = instructions_input;
  }

  pair<int, int> decode_index(int index, int size) {
    assert(0 <= index && index < size * size);
    return {index / size, index % size};
  }

  int encode_index(pair<int, int> p, int size) {
    assert(0 <= p.first && p.first < size);
    assert(0 <= p.second && p.second < size);
    return p.first * size + p.second;
  }

  inline bool is_inside(int i, int j) const {
    return (0 <= i && i < full_qubit_size) && (0 <= j && j < full_qubit_size);
  }

  inline bool is_main_qubit(int i, int j) const { return (i % 2 && j % 2); }

  void output(ostream &os, const vector<vector<int>> &path_indices,
              function<string(int)> marker, int display_width) {
    int bg;
    string bg_l, bg_r;
    for (int i = 0; i < full_qubit_size; i++) {
      for (int j = 0; j < full_qubit_size; j++) {
        string val;
        if (is_main_qubit(i, j)) {
          int index = encode_index({i / 2, j / 2}, main_qubit_size);
          val = marker(index);
        } else {
          val = ".";
        }
        if (path_indices[i][j]) {
          bg = (path_indices[i][j]) % 7 + 1;
          bg_l = "\e[4" + to_string(bg) + "m";
          bg_r = "\e[0m";
        } else {
          bg_l = "";
          bg_r = "";
        }
        os << bg_l << setw(display_width) << val << bg_r;
      }
      os << '\n';
    }
  }

  void output_x(ostream &os, const vector<vector<int>> &path_indices) {
    output(os, path_indices, [](int a) -> string { return "x"; }, 1);
  }

  void output_index(ostream &os, const vector<vector<int>> &path_indices) {
    output(
        os, path_indices, [](int a) -> string { return to_string(a); },
        main_qubit_count_digit);
  }

  void output_mpl(ostream &os, const vector<vector<int>> &path_indices, int mod) {
    for (int i = 0; i < full_qubit_size; i++) {
      for (int j = 0; j < full_qubit_size; j++) {
        string val;
        if (path_indices[i][j]) {
          os << (path_indices[i][j] + mod - 1) % mod + 1;
        } else {
          os << ".";
        }
      }
      os << '\n';
    }
  }

  void reorder_instructions_bfs() {
    int inst_size = instructions.size();

    vector<int> in_deg(inst_size);
    vector<queue<int>> instruction_queues(main_qubit_count);
    vector<int> weight(inst_size);

    queue<int> available_inst_indices;

    auto push_inst_half = [&](int inst_index, int qubit_index) -> void {
      auto &&q = instruction_queues[qubit_index];
      in_deg[inst_index] += int(!q.empty());
      q.push(inst_index);
    };

    auto push_inst = [&](int inst_index) -> void {
      two_qubit_instruction inst = instructions[inst_index];
      push_inst_half(inst_index, inst.index_start);
      push_inst_half(inst_index, inst.index_end);
      if (in_deg[inst_index] == 0) {
        available_inst_indices.push(inst_index);
      }
    };

    for (int i = 0; i < inst_size; i++) {
      push_inst(i);
    }

    /**
     * @returns new available instruction index if it exists, -1
     otherwise.
     *
     * Time complexity: O(1)
     */
    auto pop_inst = [&](int inst_index, int qubit_index) -> int {
      int ret = -1;
      auto &&q = instruction_queues[qubit_index];
      assert(q.front() == inst_index);
      q.pop();
      if (!q.empty()) {
        int next_inst_index = q.front();
        in_deg[next_inst_index] -= 1;
        if (in_deg[next_inst_index] == 0) {
          ret = next_inst_index;
        }
      }
      return ret;
    };

    int w = 0;
    while (!available_inst_indices.empty()) {
      int inst_index = available_inst_indices.front();
      two_qubit_instruction inst = instructions[inst_index];
      available_inst_indices.pop();
      int new_index;
      weight[inst_index] = w;
      w++;
      new_index = pop_inst(inst_index, inst.index_start);
      if (new_index != -1) {
        available_inst_indices.push(new_index);
      }
      new_index = pop_inst(inst_index, inst.index_end);
      if (new_index != -1) {
        available_inst_indices.push(new_index);
      }
    }

    reorder_instructions(weight);
  }

  void reorder_instructions_longest_path() {
    int inst_size = instructions.size();

    vector<int> in_deg(inst_size);
    vector<int> next_inst_indices(main_qubit_count, -1);
    // negative_weight[inst]: length of the longest path from inst
    vector<int> negative_weight(inst_size);

    auto update = [&](int inst_index, int qubit_index) -> void {
      int next_inst_index = next_inst_indices[qubit_index];
      if (next_inst_index != -1) {
        negative_weight[inst_index] =
            max(negative_weight[inst_index], negative_weight[next_inst_index] + 1);
      }
      next_inst_indices[qubit_index] = inst_index;
    };

    for (int inst_index = inst_size - 1; inst_index >= 0; inst_index--) {
      two_qubit_instruction inst = instructions[inst_index];
      update(inst_index, inst.index_start);
      update(inst_index, inst.index_end);
    }

    vector<int> weight(inst_size);
    for (int i = 0; i < inst_size; i++) {
      weight[i] = -negative_weight[i];
    }

    reorder_instructions(weight);
  }

  void reorder_instructions(const vector<int> &weight) {
    int inst_size = instructions.size();

    assert(int(weight.size()) == inst_size);

    vector<int> inst_indices(inst_size);
    iota(inst_indices.begin(), inst_indices.end(), 0);

    stable_sort(inst_indices.begin(), inst_indices.end(),
                [&](int a, int b) -> bool { return weight[a] < weight[b]; });

    vector<two_qubit_instruction> new_instructions(inst_size);
    for (int i = 0; i < inst_size; i++) {
      new_instructions[i] = instructions[inst_indices[i]];
    }

    instructions = move(new_instructions);
  }

  two_qubit_instruction _generate_random_instruction() {
    int index_start = random_main_qubit(mt);
    int index_end = index_start;
    while (index_start == index_end) {
      index_end = random_main_qubit(mt);
    }
    TWO_QUBIT_MEAS type = rand2(mt) ? MEAS_XX : MEAS_ZZ;
    return {type, index_start, index_end};
  }

 private:
  mt19937 mt;

  uniform_int_distribution<int> random_main_qubit;
  uniform_int_distribution<int> rand2;
};

/**
 * 以下のような形状を考える
 *
 * Q: 主論理量子ビット
 * .: 補助論理量子ビット
 *
 * .......
 * .Q.Q.Q.
 * .......
 * .Q.Q.Q.
 * .......
 * .Q.Q.Q.
 * .......
 *
 */

class lattice_surgery : public qubit_plane {
 public:
  explicit lattice_surgery(int n, unsigned seed = 0) : qubit_plane(n, seed) {}

  explicit lattice_surgery(qubit_plane qubit_plane_instance)
      : qubit_plane(qubit_plane_instance) {}

  inline bool is_available(int i, int j) const {
    return is_inside(i, j) && (lifetime_lattice[i][j] == 0);
  }

  inline bool is_available_ancillary(int i, int j) const {
    return is_available(i, j) && !is_main_qubit(i, j);
  }

  /**
   * decreases positive values of lifetime_lattice.
   */
  void wait(int time_delta = 1) {
    for (int i = 0; i < full_qubit_size; i++) {
      for (int j = 0; j < full_qubit_size; j++) {
        if (lifetime_lattice[i][j] > 0) {
          lifetime_lattice[i][j]--;
        }
        if (lifetime_lattice[i][j] == 0) {
          path_lattice[i][j] = 0;
        }
      }
    }
  }

  int score(int i, int j) {
    return full_qubit_size -
           min(min(i, full_qubit_size - i), min(j, full_qubit_size - j));
  }

  /**
   * @returns if there exists a path connecting `index_start` & `index_end`.
   */
  bool unite_bfs(two_qubit_instruction instruction) {
    auto [type, index_start, index_end] = instruction;
    pair<int, int> main_start = decode_index(index_start, main_qubit_size);
    pair<int, int> full_start = {main_start.first * 2 + 1, main_start.second * 2 + 1};

    pair<int, int> main_end = decode_index(index_end, main_qubit_size);
    pair<int, int> full_end = {main_end.first * 2 + 1, main_end.second * 2 + 1};

    if (!is_available(full_start.first, full_start.second) ||
        !is_available(full_end.first, full_end.second)) {
      return false;
    }

    queue<pair<int, int>> q;
    vector<vector<int>> dist(full_qubit_size, vector<int>(full_qubit_size, INF));

    auto bfs_init = [&](int i, int j) {
      if (is_available_ancillary(i, j)) {
        q.push({i, j});
        dist[i][j] = 0;
        return true;
      }
      return false;
    };

    vector<int> adjacent_indices;
    if (type == MEAS_XX) {
      adjacent_indices = {0, 1};
    } else if (type == MEAS_ZZ) {
      adjacent_indices = {2, 3};
    } else {
      throw new unreachableError();
    }
    vector<pair<int, int>> full_index_start_adjacent_qubits,
        full_index_end_adjacent_qubits;
    for (auto &&dir : adjacent_indices) {
      int di = dis[dir];
      int dj = djs[dir];
      full_index_start_adjacent_qubits.push_back(
          {full_start.first + di, full_start.second + dj});
      full_index_end_adjacent_qubits.push_back(
          {full_end.first + di, full_end.second + dj});
    }

    for (auto &&start : full_index_start_adjacent_qubits) {
      bfs_init(start.first, start.second);
    }

    while (!q.empty()) {
      auto pos = q.front();
      auto [i, j] = pos;
      q.pop();
      if (full_index_end_adjacent_qubits[0] == pos ||
          full_index_end_adjacent_qubits[1] == pos) {
        break;
      }
      for (int dir = 0; dir < 4; dir++) {
        int di = dis[dir];
        int dj = djs[dir];
        int ni = i + di;
        int nj = j + dj;
        if (is_available_ancillary(ni, nj) && dist[ni][nj] > dist[i][j] + 1) {
          dist[ni][nj] = dist[i][j] + 1;
          q.push({ni, nj});
        }
      }
    }

    int dist_adjacent_1 = dist[full_index_end_adjacent_qubits[0].first]
                              [full_index_end_adjacent_qubits[0].second];
    int dist_adjacent_2 = dist[full_index_end_adjacent_qubits[1].first]
                              [full_index_end_adjacent_qubits[1].second];
    int dist_adjacent = min(dist_adjacent_1, dist_adjacent_2);

    if (dist_adjacent == INF) {
      return false;
    }

    pair<int, int> full_adjacent;
    if (dist_adjacent == dist_adjacent_1) {
      full_adjacent = full_index_end_adjacent_qubits[0];
    } else if (dist_adjacent == dist_adjacent_2) {
      full_adjacent = full_index_end_adjacent_qubits[1];
    } else {
      throw new unreachableError();
    }

    path_index++;
    pair<int, int> full_cur = full_adjacent;
    lifetime_lattice[full_cur.first][full_cur.second] = 1;
    path_lattice[full_cur.first][full_cur.second] = path_index;
    while (full_cur != full_index_start_adjacent_qubits[0] &&
           full_cur != full_index_start_adjacent_qubits[1]) {
      auto [i, j] = full_cur;
      vector<pair<int, int>> froms;
      for (int dir = 0; dir < 4; dir++) {
        int di = dis[dir];
        int dj = djs[dir];
        int fi = i + di;
        int fj = j + dj;
        if (is_available_ancillary(fi, fj) && dist[fi][fj] + 1 == dist[i][j]) {
          froms.push_back({fi, fj});
        }
      }
      int best_fi, best_fj, best = 0;
      for (auto &&[fi, fj] : froms) {
        if (best < score(fi, fj)) {
          best = score(fi, fj);
          best_fi = fi;
          best_fj = fj;
        }
      }
      lifetime_lattice[best_fi][best_fj] = 1;
      path_lattice[best_fi][best_fj] = path_index;
      full_cur = {best_fi, best_fj};
    }
    lifetime_lattice[full_start.first][full_start.second] = 1;
    lifetime_lattice[full_end.first][full_end.second] = 1;
    path_lattice[full_start.first][full_start.second] = path_index;
    path_lattice[full_end.first][full_end.second] = path_index;
    return true;
  }

  pair<double, vector<vector<int>>> consume_instructions_by_bfs(bool verbose = true) {
    return _consume_instructions(verbose, BFS);
  }

  pair<double, vector<vector<int>>> consume_instructions_look_ahead_by_bfs(
      bool verbose = true, int depth = INF) {
    return _consume_instructions_look_ahead(verbose, BFS, depth);
  }

  pair<double, vector<vector<int>>>
  consume_instructions_look_ahead_topological_sort_by_bfs(bool verbose = true) {
    return _consume_instructions_look_ahead_topological_sort(verbose, BFS);
  }

  bool unite_without_topology(two_qubit_instruction instruction) {
    auto [type, index_start, index_end] = instruction;

    pair<int, int> main_start = decode_index(index_start, main_qubit_size);
    pair<int, int> full_start = {main_start.first * 2 + 1, main_start.second * 2 + 1};

    pair<int, int> main_end = decode_index(index_end, main_qubit_size);
    pair<int, int> full_end = {main_end.first * 2 + 1, main_end.second * 2 + 1};

    if (!is_available(full_start.first, full_start.second) ||
        !is_available(full_end.first, full_end.second)) {
      return false;
    }

    path_index++;

    lifetime_lattice[full_start.first][full_start.second] = 1;
    lifetime_lattice[full_end.first][full_end.second] = 1;
    path_lattice[full_start.first][full_start.second] = path_index;
    path_lattice[full_end.first][full_end.second] = path_index;

    return true;
  }

  pair<double, vector<vector<int>>> consume_instructions_without_topology(
      bool verbose = true) {
    return _consume_instructions(verbose, WITHOUT_TOPOLOGY);
  }

  pair<double, vector<vector<int>>> consume_instructions_look_ahead_without_topology(
      bool verbose = true) {
    return _consume_instructions_look_ahead(verbose, WITHOUT_TOPOLOGY);
  }

  pair<double, vector<vector<int>>>
  consume_instructions_look_ahead_topological_sort_without_topology(
      bool verbose = true) {
    return _consume_instructions_look_ahead_topological_sort(verbose, WITHOUT_TOPOLOGY);
  }

  pair<double, vector<vector<int>>>
  consume_instructions_look_ahead_topological_sort_queue(bool verbose,
                                                         UNITE_CALLBACK_TYPE cb_type) {
    _init_members();
    int code_beats = 0;
    vector<vector<int>> history(1);

    auto unite = [&](two_qubit_instruction i) -> bool {
      if (cb_type == BFS) {
        return unite_bfs(i);
      } else if (cb_type == WITHOUT_TOPOLOGY) {
        return unite_without_topology(i);
      } else {
        throw new unreachableError();
      }
    };

    auto wait_instruction = [&]() -> void {
      if (verbose) {
        // cerr << "\033[2J";
        cerr << (*this) << endl;
        // sleep(3);
      }
      history.push_back(vector<int>(0));
      code_beats++;
      wait();
    };

    int inst_size = instructions.size();
    vector<int> in_deg(inst_size);
    vector<queue<int>> instruction_queues(main_qubit_count);

    auto push_inst = [&](int inst_index, int qubit_index) -> void {
      auto &&q = instruction_queues[qubit_index];
      in_deg[inst_index] += int(!q.empty());
      q.push(inst_index);
    };

    for (int i = 0; i < inst_size; i++) {
      two_qubit_instruction inst = instructions[i];
      push_inst(i, inst.index_start);
      push_inst(i, inst.index_end);
    }

    queue<int> available_inst_indices, new_available_inst_indices, failed_inst_indices;
    for (int i = 0; i < inst_size; i++) {
      if (in_deg[i] == 0) {
        available_inst_indices.push(i);
      }
    }

    /**
     * @returns new available instruction index if it exists, -1
     otherwise.
     *
     * Time complexity: O(1)
     */
    auto pop_inst = [&](int inst_index, int qubit_index) -> int {
      int ret = -1;
      auto &&q = instruction_queues[qubit_index];
      assert(q.front() == inst_index);
      q.pop();
      if (!q.empty()) {
        int next_inst_index = q.front();
        in_deg[next_inst_index] -= 1;
        if (in_deg[next_inst_index] == 0) {
          ret = next_inst_index;
        }
      }
      return ret;
    };

    progress p(string("look ahead (queue) ") + to_string(cb_type));
    p.show();

    int consumed_inst_count = 0;
    while (consumed_inst_count < int(instructions.size())) {
      while (!available_inst_indices.empty()) {
        int inst_index = available_inst_indices.front();
        available_inst_indices.pop();
        two_qubit_instruction inst = instructions[inst_index];
        if (unite(inst)) {
          int new_index;
          consumed_inst_count++;
          history[code_beats].push_back(inst_index);
          new_index = pop_inst(inst_index, inst.index_start);
          if (new_index != -1) {
            new_available_inst_indices.push(new_index);
          }
          new_index = pop_inst(inst_index, inst.index_end);
          if (new_index != -1) {
            new_available_inst_indices.push(new_index);
          }
          if (verbose) {
            cerr << (inst_index + 1) << ' ' << inst << endl;
          }
        } else {
          failed_inst_indices.push(inst_index);
        }
      }
      available_inst_indices = move(failed_inst_indices);
      failed_inst_indices = queue<int>();
      while (!new_available_inst_indices.empty()) {
        available_inst_indices.push(new_available_inst_indices.front());
        new_available_inst_indices.pop();
      }
      wait_instruction();

      p.update(100.0 * consumed_inst_count / inst_size);
    }
    history.pop_back();

    p.update(100);

    double through_put = (double)instructions.size() / code_beats;
    if (verbose) {
      cerr << "Through Put: " << instructions.size() << "/" << code_beats << " = "
           << through_put << endl;
    }
    return {through_put, history};
  }

  bool check_history(vector<vector<int>> history) {
    int inst_size = instructions.size();
    vector<int> inst_count(inst_size);
    vector<int> main_qubit_inst(main_qubit_count, -1);
    for (auto &&row : history) {
      for (auto &&inst_index : row) {
        two_qubit_instruction inst = instructions[inst_index];
        inst_count[inst_index]++;
        if (main_qubit_inst[inst.index_start] >= inst_index) {
          return false;
        }
        main_qubit_inst[inst.index_start] = inst_index;
        if (main_qubit_inst[inst.index_end] >= inst_index) {
          return false;
        }
        main_qubit_inst[inst.index_end] = inst_index;
      }
    }
    for (int i = 0; i < inst_size; i++) {
      if (inst_count[i] != 1) {
        return false;
      }
    }
    return true;
  }

  friend ostream &operator<<(ostream &os, lattice_surgery &ls) {
    ls.output_index(os, ls.path_lattice);
    return os;
  }

 private:
  int path_index;
  vector<vector<int>> lifetime_lattice;
  vector<vector<int>> path_lattice;

  void _init_members() {
    path_index = 0;
    lifetime_lattice =
        vector<vector<int>>(full_qubit_size, vector<int>(full_qubit_size, 0));
    path_lattice =
        vector<vector<int>>(full_qubit_size, vector<int>(full_qubit_size, 0));
  }

  pair<double, vector<vector<int>>> _consume_instructions(bool verbose,
                                                          UNITE_CALLBACK_TYPE cb_type) {
    _init_members();
    int code_beats = 0;
    vector<vector<int>> history(1);

    auto unite = [&](two_qubit_instruction i) -> bool {
      if (cb_type == BFS) {
        return unite_bfs(i);
      } else if (cb_type == WITHOUT_TOPOLOGY) {
        return unite_without_topology(i);
      } else {
        throw new unreachableError();
      }
    };

    auto wait_instruction = [&]() -> void {
      if (verbose) {
        // cerr << "\033[2J";
        cerr << (*this) << endl;
        // sleep(3);
      }
      history.push_back(vector<int>(0));
      code_beats++;
      wait();
    };

    progress p(string("2D ") + to_string(cb_type));
    p.show();

    int inst_size = instructions.size();
    for (int i = 0; i < inst_size; i++) {
      auto inst = instructions[i];
      while (!unite(inst)) {
        unite_without_topology(inst);
        wait_instruction();
      }
      if (verbose) {
        cerr << inst << endl;
      }
      history[code_beats].push_back(i);

      p.update(100.0 * i / inst_size);
    }
    wait_instruction();
    history.pop_back();

    p.update(100);

    double through_put = (double)instructions.size() / code_beats;
    if (verbose) {
      cerr << "Through Put: " << instructions.size() << "/" << code_beats << " = "
           << through_put << endl;
    }
    return {through_put, history};
  }

  pair<double, vector<vector<int>>> _consume_instructions_look_ahead(
      bool verbose, UNITE_CALLBACK_TYPE cb_type, int depth = INF) {
    _init_members();
    int code_beats = 0;
    vector<vector<int>> history(1);

    auto unite = [&](two_qubit_instruction i) -> bool {
      if (cb_type == BFS) {
        return unite_bfs(i);
      } else if (cb_type == WITHOUT_TOPOLOGY) {
        return unite_without_topology(i);
      } else {
        throw new unreachableError();
      }
    };

    auto wait_instruction = [&]() -> void {
      if (verbose) {
        // cerr << "\033[2J";
        cerr << (*this) << endl;
        // sleep(3);
      }
      history.push_back(vector<int>(0));
      code_beats++;
      wait();
    };

    progress p(string("look ahead ") + to_string(cb_type));
    p.show();

    int inst_size = instructions.size();
    vector<int> consumed(inst_size);
    for (int i = 0; i < inst_size; i++) {
      if (consumed[i]) {
        continue;
      }

      int reserved_count = 0;
      vector<int> reserved(main_qubit_count);
      for (int j = i; j < min(i + depth, inst_size); j++) {
        if (consumed[j]) {
          continue;
        }
        two_qubit_instruction inst = instructions[j];
        if (!reserved[inst.index_start] && !reserved[inst.index_end] &&
            unite(instructions[j])) {
          consumed[j] = true;
          if (verbose) {
            cerr << (j + 1) << ' ' << instructions[j] << endl;
          }
          history[code_beats].push_back(j);
        }
        if (!reserved[inst.index_start]) {
          reserved[inst.index_start] = true;
          reserved_count++;
        }
        if (!reserved[inst.index_end]) {
          reserved[inst.index_end] = true;
          reserved_count++;
        }
        if (reserved_count == main_qubit_count) {
          break;
        }
      }
      wait_instruction();

      p.update(100.0 * i / inst_size);
    }
    history.pop_back();

    p.update(100);

    double through_put = (double)instructions.size() / code_beats;
    if (verbose) {
      cerr << "Through Put: " << instructions.size() << "/" << code_beats << " = "
           << through_put << endl;
    }
    return {through_put, history};
  }

  pair<double, vector<vector<int>>> _consume_instructions_look_ahead_topological_sort(
      bool verbose, UNITE_CALLBACK_TYPE cb_type) {
    _init_members();
    int code_beats = 0;
    vector<vector<int>> history(1);

    auto unite = [&](two_qubit_instruction i) -> bool {
      if (cb_type == BFS) {
        return unite_bfs(i);
      } else if (cb_type == WITHOUT_TOPOLOGY) {
        return unite_without_topology(i);
      } else {
        throw new unreachableError();
      }
    };

    auto wait_instruction = [&]() -> void {
      if (verbose) {
        // cerr << "\033[2J";
        cerr << (*this) << endl;
        // sleep(3);
      }
      history.push_back(vector<int>(0));
      code_beats++;
      wait();
    };

    int inst_size = instructions.size();
    vector<int> in_deg(inst_size);
    vector<queue<int>> instruction_queues(main_qubit_count);

    auto push_inst = [&](int inst_index, int qubit_index) -> void {
      auto &&q = instruction_queues[qubit_index];
      in_deg[inst_index] += int(!q.empty());
      q.push(inst_index);
    };

    for (int i = 0; i < inst_size; i++) {
      two_qubit_instruction inst = instructions[i];
      push_inst(i, inst.index_start);
      push_inst(i, inst.index_end);
    }

    priority_queue<int, vector<int>, greater<int>> available_inst_indices,
        new_available_inst_indices;
    for (int i = 0; i < inst_size; i++) {
      if (in_deg[i] == 0) {
        available_inst_indices.push(i);
      }
    }

    /**
     * @returns new available instruction index if it exists, -1 otherwise.
     *
     * Time complexity: O(1)
     */
    auto pop_inst = [&](int inst_index, int qubit_index) -> int {
      int ret = -1;
      auto &&q = instruction_queues[qubit_index];
      assert(q.front() == inst_index);
      q.pop();
      if (!q.empty()) {
        int next_inst_index = q.front();
        in_deg[next_inst_index] -= 1;
        if (in_deg[next_inst_index] == 0) {
          ret = next_inst_index;
        }
      }
      return ret;
    };

    progress p(string("look ahead (top-sort) ") + to_string(cb_type));
    p.show();

    int consumed_inst_count = 0;
    while (consumed_inst_count < inst_size) {
      while (!available_inst_indices.empty()) {
        int inst_index = available_inst_indices.top();
        available_inst_indices.pop();
        two_qubit_instruction inst = instructions[inst_index];
        if (unite(inst)) {
          int new_index;
          consumed_inst_count++;
          history[code_beats].push_back(inst_index);
          new_index = pop_inst(inst_index, inst.index_start);
          if (new_index != -1) {
            new_available_inst_indices.push(new_index);
          }
          new_index = pop_inst(inst_index, inst.index_end);
          if (new_index != -1) {
            new_available_inst_indices.push(new_index);
          }
          if (verbose) {
            cerr << (inst_index + 1) << ' ' << inst << endl;
          }
        } else {
          new_available_inst_indices.push(inst_index);
        }
      }
      available_inst_indices = move(new_available_inst_indices);
      new_available_inst_indices = decltype(new_available_inst_indices)();
      wait_instruction();

      p.update(100.0 * consumed_inst_count / inst_size);
    }
    history.pop_back();

    p.update(100.0);

    double through_put = (double)inst_size / code_beats;
    if (verbose) {
      cerr << "Through Put: " << inst_size << "/" << code_beats << " = " << through_put
           << endl;
    }
    return {through_put, history};
  }
};

class lattice_surgery_3d : public qubit_plane {
 public:
  explicit lattice_surgery_3d(int n, unsigned seed = 0) : qubit_plane(n, seed) {}

  explicit lattice_surgery_3d(qubit_plane qubit_plane_instance)
      : qubit_plane(qubit_plane_instance) {}

  inline bool is_valid_time(int t) { return (0 <= t && t < code_beats); }

  inline bool is_available_3d(int t, int i, int j) {
    return is_valid_time(t) && is_inside(i, j) && (!stacked_lattice[t][i][j]);
  }

  inline bool is_available_ancillary_3d(int t, int i, int j) {
    return is_available_3d(t, i, j) && (!is_main_qubit(i, j));
  };

  /**
   * @returns if the top lattice of `stacked_lattice` has been used.
   */
  bool unite_bfs_3d(two_qubit_instruction instruction) {
    bool broken_debug;

    auto [type, index_start, index_end] = instruction;

    pair<int, int> main_start = decode_index(index_start, main_qubit_size);
    pair<int, int> full_start = {main_start.first * 2 + 1, main_start.second * 2 + 1};

    pair<int, int> main_end = decode_index(index_end, main_qubit_size);
    pair<int, int> full_end = {main_end.first * 2 + 1, main_end.second * 2 + 1};

    queue<int> q;
    vector<vector<vector<int>>> dist(
        code_beats,
        vector<vector<int>>(full_qubit_size, vector<int>(full_qubit_size, INF)));

    auto bfs_init = [&](int t, int i, int j) {
      if (is_available_ancillary_3d(t, i, j)) {
        q.push(encode_index_3d({t, i, j}, full_qubit_size));
        dist[t][i][j] = 0;
        return true;
      }
      return false;
    };

    vector<int> adjacent_indices;
    if (type == MEAS_XX) {
      adjacent_indices = {0, 1};
    } else if (type == MEAS_ZZ) {
      adjacent_indices = {2, 3};
    } else {
      cerr << "non-existent type: " << type << endl;
      throw new unreachableError();
    }

    vector<pair<int, int>> full_index_start_adjacent_qubits,
        full_index_end_adjacent_qubits;
    for (auto &&dir : adjacent_indices) {
      int di = dis[dir];
      int dj = djs[dir];
      full_index_start_adjacent_qubits.push_back(
          {full_start.first + di, full_start.second + dj});
      full_index_end_adjacent_qubits.push_back(
          {full_end.first + di, full_end.second + dj});
    }

    bool arrived_goal = false;
    int start_depth = -1;
    for (start_depth = heights[index_start]; start_depth < code_beats; start_depth++) {
      if (!is_available_3d(start_depth, full_start.first, full_start.second)) {
        continue;
      }
      for (auto &&start : full_index_start_adjacent_qubits) {
        bfs_init(start_depth, start.first, start.second);
      }

      // cerr << "bfs start" << endl;
      while (!q.empty()) {
        auto [t, i, j] = decode_index_3d(q.front(), full_qubit_size);
        q.pop();
        auto pos = make_pair(i, j);
        if ((full_index_end_adjacent_qubits[0] == pos ||
             full_index_end_adjacent_qubits[1] == pos) &&
            heights[index_end] <= t &&
            is_available_3d(t, full_end.first, full_end.second)) {
          arrived_goal = true;
        }
        for (int dir = 0; dir < 6; dir++) {
          int di = dis3d[dir];
          int dj = djs3d[dir];
          int dt = dts3d[dir];
          int ni = i + di;
          int nj = j + dj;
          int nt = t + dt;
          if (!is_available_ancillary_3d(nt, ni, nj)) {
            continue;
          }
          if (dist[nt][ni][nj] > dist[t][i][j] + 1) {
            dist[nt][ni][nj] = dist[t][i][j] + 1;
            q.push(encode_index_3d({nt, ni, nj}, full_qubit_size));
          }
        }
      }
      // cerr << "bfs end" << endl;
      if (arrived_goal) {
        break;
      }
    }

    if (!arrived_goal) {
      cerr << "It could not find a path connecting given two qubits." << endl;
      throw new unreachableError();
    }

    int dist_adjacent = INF;
    tuple<int, int, int> min_tup;
    broken_debug = false;
    for (int end_depth = heights[index_end]; end_depth < code_beats; end_depth++) {
      if (!is_available_3d(end_depth, full_end.first, full_end.second)) {
        continue;
      }
      for (auto &&end : full_index_end_adjacent_qubits) {
        if (dist_adjacent > dist[end_depth][end.first][end.second]) {
          dist_adjacent = dist[end_depth][end.first][end.second];
          min_tup = {end_depth, end.first, end.second};
        }
      }
      if (dist_adjacent < INF) {
        broken_debug = true;
        break;
      }
    }
    if (!broken_debug) {
      cerr << "There exists no space around the `index_end` qubit." << endl;
      throw new unreachableError();
    }

    int end_depth = get<0>(min_tup);

    path_index++;
    tuple<int, int, int> full_cur = min_tup;
    stacked_lattice[get<0>(full_cur)][get<1>(full_cur)][get<2>(full_cur)] = path_index;
    int t_max = max(start_depth, end_depth);
    while (dist[get<0>(full_cur)][get<1>(full_cur)][get<2>(full_cur)]) {
      // cerr << dist[get<0>(full_cur)][get<1>(full_cur)]
      //             [get<2>(full_cur)]
      //      << endl;
      auto [t, i, j] = full_cur;
      t_max = max(t_max, t);
      broken_debug = false;
      for (int dir = 0; dir < 6; dir++) {
        int di = dis3d[dir];
        int dj = djs3d[dir];
        int dt = dts3d[dir];
        int fi = i + di;
        int fj = j + dj;
        int ft = t + dt;
        if (is_available_ancillary_3d(ft, fi, fj) &&
            dist[ft][fi][fj] + 1 == dist[t][i][j]) {
          stacked_lattice[ft][fi][fj] = path_index;
          full_cur = {ft, fi, fj};
          broken_debug = true;
          break;
        }
      }
      if (!broken_debug) {
        cerr << "It could not rollback the path." << endl;
        throw new unreachableError();
      }
    }
    stacked_lattice[start_depth][full_start.first][full_start.second] = path_index;
    stacked_lattice[end_depth][full_end.first][full_end.second] = path_index;

    // cerr << end_depth << ' ' << heights[index_end] << endl;

    assert(heights[index_start] < start_depth + 1);
    heights[index_start] = start_depth + 1;
    assert(heights[index_end] < end_depth + 1);
    heights[index_end] = end_depth + 1;

    return (t_max == code_beats - 1);
  }

  /**
   * @returns if the top lattice of `stacked_lattice` has been used.
   */
  bool unite_dijkstra_3d(two_qubit_instruction instruction,
                         function<ll(int, int, int, int, int, int)> cost_func) {
    bool broken_debug;

    auto [type, index_start, index_end] = instruction;

    pair<int, int> main_start = decode_index(index_start, main_qubit_size);
    pair<int, int> full_start = {main_start.first * 2 + 1, main_start.second * 2 + 1};

    pair<int, int> main_end = decode_index(index_end, main_qubit_size);
    pair<int, int> full_end = {main_end.first * 2 + 1, main_end.second * 2 + 1};

    struct Q {
      ll key;
      int index_3d;
      bool operator<(Q r) const { return key > r.key; }
    };
    priority_queue<Q> pq;
    vector<vector<vector<ll>>> dist(
        code_beats,
        vector<vector<ll>>(full_qubit_size, vector<ll>(full_qubit_size, INFll)));

    auto dijkstra_init = [&](int t, int i, int j) {
      if (is_available_ancillary_3d(t, i, j)) {
        pq.push({0, encode_index_3d({t, i, j}, full_qubit_size)});
        dist[t][i][j] = 0;
        return true;
      }
      return false;
    };

    vector<int> adjacent_indices;
    if (type == MEAS_XX) {
      adjacent_indices = {0, 1};
    } else if (type == MEAS_ZZ) {
      adjacent_indices = {2, 3};
    } else {
      cerr << "non-existent type: " << type << endl;
      throw new unreachableError();
    }

    vector<pair<int, int>> full_index_start_adjacent_qubits,
        full_index_end_adjacent_qubits;
    for (auto &&dir : adjacent_indices) {
      int di = dis[dir];
      int dj = djs[dir];
      full_index_start_adjacent_qubits.push_back(
          {full_start.first + di, full_start.second + dj});
      full_index_end_adjacent_qubits.push_back(
          {full_end.first + di, full_end.second + dj});
    }

    bool arrived_goal = false;
    int start_depth = -1;
    for (start_depth = heights[index_start]; start_depth < code_beats; start_depth++) {
      if (!is_available_3d(start_depth, full_start.first, full_start.second)) {
        continue;
      }
      for (auto &&start : full_index_start_adjacent_qubits) {
        dijkstra_init(start_depth, start.first, start.second);
      }

      while (!pq.empty()) {
        auto [key, index_3d] = pq.top();
        pq.pop();
        auto [t, i, j] = decode_index_3d(index_3d, full_qubit_size);
        if (dist[t][i][j] < key) {
          continue;
        }
        auto pos = make_pair(i, j);
        if ((full_index_end_adjacent_qubits[0] == pos ||
             full_index_end_adjacent_qubits[1] == pos) &&
            heights[index_end] <= t &&
            is_available_3d(t, full_end.first, full_end.second)) {
          arrived_goal = true;
        }
        for (int dir = 0; dir < 6; dir++) {
          int di = dis3d[dir];
          int dj = djs3d[dir];
          int dt = dts3d[dir];
          int ni = i + di;
          int nj = j + dj;
          int nt = t + dt;
          if (!is_available_ancillary_3d(nt, ni, nj)) {
            continue;
          }
          ll nd = dist[t][i][j] + cost_func(t, i, j, nt, ni, nj);
          if (dist[nt][ni][nj] > nd) {
            dist[nt][ni][nj] = nd;
            int index_3d = encode_index_3d({nt, ni, nj}, full_qubit_size);
            pq.push({nd, index_3d});
          }
        }
      }
      if (arrived_goal) {
        break;
      }
    }

    if (!arrived_goal) {
      cerr << "It could not find a path connecting given two qubits." << endl;
      throw new unreachableError();
    }

    ll dist_adjacent = INFll;
    tuple<int, int, int> min_tup;
    broken_debug = false;
    for (int end_depth = heights[index_end]; end_depth < code_beats; end_depth++) {
      if (!is_available_3d(end_depth, full_end.first, full_end.second)) {
        continue;
      }
      for (auto &&end : full_index_end_adjacent_qubits) {
        if (dist_adjacent > dist[end_depth][end.first][end.second]) {
          dist_adjacent = dist[end_depth][end.first][end.second];
          min_tup = {end_depth, end.first, end.second};
        }
      }
      if (dist_adjacent < INFll) {
        broken_debug = true;
        break;
      }
    }
    if (!broken_debug) {
      cerr << "There exists no space around the `index_end` qubit." << endl;
      throw new unreachableError();
    }

    int end_depth = get<0>(min_tup);

    path_index++;
    tuple<int, int, int> full_cur = min_tup;
    stacked_lattice[get<0>(full_cur)][get<1>(full_cur)][get<2>(full_cur)] = path_index;
    int t_min = min(start_depth, end_depth);
    int t_max = max(start_depth, end_depth);
    while (dist[get<0>(full_cur)][get<1>(full_cur)][get<2>(full_cur)]) {
      // cerr << dist[get<0>(full_cur)][get<1>(full_cur)]
      //             [get<2>(full_cur)]
      //      << endl;
      auto [t, i, j] = full_cur;
      t_min = min(t_min, t);
      t_max = max(t_max, t);
      broken_debug = false;
      for (int dir = 0; dir < 6; dir++) {
        int di = dis3d[dir];
        int dj = djs3d[dir];
        int dt = dts3d[dir];
        int fi = i + di;
        int fj = j + dj;
        int ft = t + dt;
        if (is_available_ancillary_3d(ft, fi, fj) &&
            dist[ft][fi][fj] + cost_func(ft, fi, fj, t, i, j) == dist[t][i][j]) {
          stacked_lattice[ft][fi][fj] = path_index;
          full_cur = {ft, fi, fj};
          broken_debug = true;
          break;
        }
      }
      if (!broken_debug) {
        cerr << "It could not rollback the path." << endl;
        throw new unreachableError();
      }
    }
    stacked_lattice[start_depth][full_start.first][full_start.second] = path_index;
    stacked_lattice[end_depth][full_end.first][full_end.second] = path_index;

    // cerr << t_min << ' ' << start_depth << ' ' << end_depth << ' ' <<
    // t_max
    //      << endl;

    assert(heights[index_start] < start_depth + 1);
    heights[index_start] = start_depth + 1;
    assert(heights[index_end] < end_depth + 1);
    heights[index_end] = end_depth + 1;

    return (t_max == code_beats - 1);
  }

  /**
   * @returns if the top lattice of `stacked_lattice` has been used.
   */
  bool unite_without_topology_3d(two_qubit_instruction instruction) {
    auto [type, index_start, index_end] = instruction;

    pair<int, int> main_start = decode_index(index_start, main_qubit_size);
    pair<int, int> full_start = {main_start.first * 2 + 1, main_start.second * 2 + 1};

    pair<int, int> main_end = decode_index(index_end, main_qubit_size);
    pair<int, int> full_end = {main_end.first * 2 + 1, main_end.second * 2 + 1};

    ++path_index;

    stacked_lattice[heights[index_start]][full_start.first][full_start.second] =
        path_index;
    stacked_lattice[heights[index_end]][full_end.first][full_end.second] = path_index;
    heights[index_start]++;
    heights[index_end]++;
    return (code_beats == heights[index_start] || code_beats == heights[index_end]);
  }

  double consume_instructions(bool verbose, UNITE_CALLBACK_TYPE_3D cb_type) {
    return _consume_instructions(verbose, cb_type);
  }

  double consume_instructions_by_bfs_3d(bool verbose = true) {
    return _consume_instructions(verbose, BFS_3D);
  }

  double consume_instructions_without_topology(bool verbose = true) {
    return _consume_instructions(verbose, WITHOUT_TOPOLOGY_3D);
  }

  friend ostream &operator<<(ostream &os, lattice_surgery_3d &ls3) {
    for (int t = 0; t < ls3.code_beats; t++) {
      ls3.output_index(os, ls3.stacked_lattice[t]);
      os << '\n';
    }
    return os;
  }

 private:
  int path_index;
  int code_beats;

  vector<vector<vector<int>>> stacked_lattice;
  vector<int> heights;

  void _init_members() {
    path_index = 0;
    code_beats = 1;
    stacked_lattice = vector<vector<vector<int>>>(
        code_beats, vector<vector<int>>(full_qubit_size, vector<int>(full_qubit_size)));
    heights = vector<int>(main_qubit_count);
  }

  void _stack_lattice() {
    code_beats++;
    stacked_lattice.push_back(
        vector<vector<int>>(full_qubit_size, vector<int>(full_qubit_size)));
  }

  tuple<int, int, int> decode_index_3d(int index, int size) {
    assert(0 <= index && index < code_beats * size * size);
    int j = index % size;
    int q = index / size;
    int time = q / size;
    int i = q % size;
    return {time, i, j};
  }

  int encode_index_3d(tuple<int, int, int> tup, int size) {
    assert(0 <= get<0>(tup) && get<0>(tup) < code_beats);
    assert(0 <= get<1>(tup) && get<1>(tup) < size);
    assert(0 <= get<2>(tup) && get<2>(tup) < size);
    return (get<0>(tup) * size + get<1>(tup)) * size + get<2>(tup);
  }

  double _consume_instructions(bool verbose, UNITE_CALLBACK_TYPE_3D cb_type) {
    _init_members();

    auto unite = [&](two_qubit_instruction inst) -> bool {
      if (cb_type == BFS_3D) {
        return unite_bfs_3d(inst);
      } else if (cb_type == DIJKSTRA_3D_BFS) {
        return unite_dijkstra_3d(
            inst,
            [&](int t, int i, int j, int nt, int ni, int nj) -> ll { return INF; });
      } else if (cb_type == DIJKSTRA_3D_LAYER_BASED_COST) {
        return unite_dijkstra_3d(
            inst, [&](int t, int i, int j, int nt, int ni, int nj) -> ll {
              return max(t, nt) + 1;
            });
      } else if (cb_type == DIJKSTRA_3D_LAYER_CHANGE_COST) {
        return unite_dijkstra_3d(
            inst, [&](int t, int i, int j, int nt, int ni, int nj) -> ll {
              return (t == nt ? 1 : INF);
            });
      } else if (cb_type == DIJKSTRA_3D_LAYER_MIX_COST) {
        return unite_dijkstra_3d(
            inst, [&](int t, int i, int j, int nt, int ni, int nj) -> ll {
              return (t == nt ? t + 1 : INF);
            });
      } else if (cb_type == DIJKSTRA_3D_LAYER_EXP_COST) {
        return unite_dijkstra_3d(
            inst, [&](int t, int i, int j, int nt, int ni, int nj) -> ll {
              int shift = min((code_beats - max(t, nt)), 29);
              return INF >> shift;
            });
      } else if (cb_type == WITHOUT_TOPOLOGY_3D) {
        return unite_without_topology_3d(inst);
      } else {
        throw new unreachableError();
      }
    };

    progress p(string("3D ") + to_string(cb_type));
    p.show();

    int inst_size = instructions.size();
    for (int i = 0; i < inst_size; i++) {
      auto inst = instructions[i];
      if (verbose) {
        cerr << inst << endl;
      }
      if (unite(inst)) {
        _stack_lattice();
      }

      p.update(100.0 * i / inst_size);
    }
    code_beats--;
    stacked_lattice.pop_back();

    if (verbose) {
      cerr << (*this) << endl;
    }

    p.update(100);

    double through_put = (double)instructions.size() / code_beats;
    if (verbose) {
      cerr << "Through Put: " << instructions.size() << "/" << code_beats << " = "
           << through_put << endl;
    }
    return through_put;
  }
};

class lattice_surgery_pj : public qubit_plane {
 public:
  explicit lattice_surgery_pj(int n, unsigned seed = 0) : qubit_plane(n, seed) {}

  explicit lattice_surgery_pj(qubit_plane qubit_plane_instance)
      : qubit_plane(qubit_plane_instance) {}

  inline bool is_available(int i, int j) const { return is_inside(i, j); }

  inline bool is_available_ancillary(int i, int j) const {
    return is_available(i, j) && !is_main_qubit(i, j);
  }

  vector<pair<int, int>> find_2d_path_bfs(two_qubit_instruction instruction) {
    auto [type, index_start, index_end] = instruction;

    pair<int, int> main_start = decode_index(index_start, main_qubit_size);
    pair<int, int> full_start = {main_start.first * 2 + 1, main_start.second * 2 + 1};

    pair<int, int> main_end = decode_index(index_end, main_qubit_size);
    pair<int, int> full_end = {main_end.first * 2 + 1, main_end.second * 2 + 1};

    queue<pair<int, int>> q;
    vector<vector<int>> dist(full_qubit_size, vector<int>(full_qubit_size, INF));

    auto bfs_init = [&](int i, int j) {
      if (is_available_ancillary(i, j)) {
        q.push({i, j});
        dist[i][j] = 0;
        return true;
      }
      return false;
    };

    vector<int> adjacent_indices;
    if (type == MEAS_XX) {
      adjacent_indices = {0, 1};
    } else if (type == MEAS_ZZ) {
      adjacent_indices = {2, 3};
    } else {
      throw new unreachableError();
    }
    vector<pair<int, int>> full_index_start_adjacent_qubits,
        full_index_end_adjacent_qubits;
    for (auto &&dir : adjacent_indices) {
      int di = dis[dir];
      int dj = djs[dir];
      full_index_start_adjacent_qubits.push_back(
          {full_start.first + di, full_start.second + dj});
      full_index_end_adjacent_qubits.push_back(
          {full_end.first + di, full_end.second + dj});
    }

    for (auto &&start : full_index_start_adjacent_qubits) {
      bfs_init(start.first, start.second);
    }

    while (!q.empty()) {
      auto [i, j] = q.front();
      q.pop();
      for (int dir = 0; dir < 4; dir++) {
        int di = dis[dir];
        int dj = djs[dir];
        int ni = i + di;
        int nj = j + dj;
        if (is_available_ancillary(ni, nj) && dist[ni][nj] > dist[i][j] + 1) {
          dist[ni][nj] = dist[i][j] + 1;
          q.push({ni, nj});
        }
      }
    }

    int dist_adjacent_1 = dist[full_index_end_adjacent_qubits[0].first]
                              [full_index_end_adjacent_qubits[0].second];
    int dist_adjacent_2 = dist[full_index_end_adjacent_qubits[1].first]
                              [full_index_end_adjacent_qubits[1].second];
    int dist_adjacent = min(dist_adjacent_1, dist_adjacent_2);

    pair<int, int> full_adjacent;
    if (dist_adjacent == dist_adjacent_1) {
      full_adjacent = full_index_end_adjacent_qubits[0];
    } else if (dist_adjacent == dist_adjacent_2) {
      full_adjacent = full_index_end_adjacent_qubits[1];
    } else {
      throw new unreachableError();
    }

    pair<int, int> full_cur = full_adjacent;
    vector<pair<int, int>> path = {full_end};
    path.push_back(full_cur);
    while (full_cur != full_index_start_adjacent_qubits[0] &&
           full_cur != full_index_start_adjacent_qubits[1]) {
      auto [i, j] = full_cur;
      for (int dir = 0; dir < 4; dir++) {
        int di = dis[dir];
        int dj = djs[dir];
        int fi = i + di;
        int fj = j + dj;
        if (is_available_ancillary(fi, fj) && dist[fi][fj] + 1 == dist[i][j]) {
          full_cur = {fi, fj};
          path.push_back(full_cur);
          break;
        }
      }
    }
    path.push_back(full_start);
    reverse(path.begin(), path.end());
    return path;
  }

  vector<pair<int, int>> find_2d_path_dijkstra(two_qubit_instruction instruction,
                                               function<ll(int, int)> cost_func) {
    auto [type, index_start, index_end] = instruction;

    pair<int, int> main_start = decode_index(index_start, main_qubit_size);
    pair<int, int> full_start = {main_start.first * 2 + 1, main_start.second * 2 + 1};

    pair<int, int> main_end = decode_index(index_end, main_qubit_size);
    pair<int, int> full_end = {main_end.first * 2 + 1, main_end.second * 2 + 1};

    struct Q {
      ll key;
      int i;
      int j;
      bool operator<(Q r) const { return key > r.key; }
    };
    priority_queue<Q> pq;
    vector<vector<ll>> dist(full_qubit_size, vector<ll>(full_qubit_size, INFll));

    auto dijkstra_init = [&](int i, int j) {
      if (is_available_ancillary(i, j)) {
        pq.push({0, i, j});
        dist[i][j] = 0;
        return true;
      }
      return false;
    };

    vector<int> adjacent_indices;
    if (type == MEAS_XX) {
      adjacent_indices = {0, 1};
    } else if (type == MEAS_ZZ) {
      adjacent_indices = {2, 3};
    } else {
      throw new unreachableError();
    }
    vector<pair<int, int>> full_index_start_adjacent_qubits,
        full_index_end_adjacent_qubits;
    for (auto &&dir : adjacent_indices) {
      int di = dis[dir];
      int dj = djs[dir];
      full_index_start_adjacent_qubits.push_back(
          {full_start.first + di, full_start.second + dj});
      full_index_end_adjacent_qubits.push_back(
          {full_end.first + di, full_end.second + dj});
    }

    for (auto &&start : full_index_start_adjacent_qubits) {
      dijkstra_init(start.first, start.second);
    }

    while (!pq.empty()) {
      auto [d, i, j] = pq.top();
      pq.pop();

      if (dist[i][j] < d) {
        continue;
      }

      auto pos = make_pair(i, j);
      if (full_index_end_adjacent_qubits[0] == pos ||
          full_index_end_adjacent_qubits[1] == pos) {
        break;
      }

      for (int dir = 0; dir < 4; dir++) {
        int di = dis[dir];
        int dj = djs[dir];
        int ni = i + di;
        int nj = j + dj;
        if (is_available_ancillary(ni, nj)) {
          ll nd = dist[i][j] + cost_func(heights[i][j], heights[ni][nj]);
          if (dist[ni][nj] > nd) {
            dist[ni][nj] = nd;
            pq.push({nd, ni, nj});
          }
        }
      }
    }

    ll dist_adjacent_1 = dist[full_index_end_adjacent_qubits[0].first]
                             [full_index_end_adjacent_qubits[0].second];
    ll dist_adjacent_2 = dist[full_index_end_adjacent_qubits[1].first]
                             [full_index_end_adjacent_qubits[1].second];
    ll dist_adjacent = min(dist_adjacent_1, dist_adjacent_2);

    pair<int, int> full_adjacent;
    if (dist_adjacent == dist_adjacent_1) {
      full_adjacent = full_index_end_adjacent_qubits[0];
    } else if (dist_adjacent == dist_adjacent_2) {
      full_adjacent = full_index_end_adjacent_qubits[1];
    } else {
      throw new unreachableError();
    }

    pair<int, int> full_cur = full_adjacent;
    vector<pair<int, int>> path = {full_end};
    path.push_back(full_cur);
    while (full_cur != full_index_start_adjacent_qubits[0] &&
           full_cur != full_index_start_adjacent_qubits[1]) {
      auto [i, j] = full_cur;
      for (int dir = 0; dir < 4; dir++) {
        int di = dis[dir];
        int dj = djs[dir];
        int fi = i + di;
        int fj = j + dj;
        if (is_available_ancillary(fi, fj) &&
            dist[fi][fj] + cost_func(heights[fi][fj], heights[i][j]) == dist[i][j]) {
          full_cur = {fi, fj};
          path.push_back(full_cur);
          break;
        }
      }
    }
    path.push_back(full_start);
    reverse(path.begin(), path.end());
    return path;
  }

  vector<pair<int, int>> find_2d_path_satisfying_condition_dijkstra(
      two_qubit_instruction instruction, function<ll(int, int)> cost_func) {
    auto [type, index_start, index_end] = instruction;
    pair<int, int> main_start = decode_index(index_start, main_qubit_size);
    pair<int, int> full_start = {main_start.first * 2 + 1, main_start.second * 2 + 1};
    pair<int, int> main_end = decode_index(index_end, main_qubit_size);
    pair<int, int> full_end = {main_end.first * 2 + 1, main_end.second * 2 + 1};

    auto encode_state = [&](int i, int j, int dir, int par) -> int {
      return (encode_index({i, j}, full_qubit_size) * 4 + dir) * 2 + par;
    };
    auto decode_state = [&](int state) -> tuple<int, int, int, int> {
      int par = state % 2;
      state /= 2;
      int dir = state % 4;
      state /= 4;
      auto [i, j] = decode_index(state, full_qubit_size);
      return {i, j, dir, par};
    };
    int state_size = full_qubit_count * 8;

    struct Q {
      ll key;
      int state;
      bool operator<(Q r) const { return key > r.key; }
    };
    priority_queue<Q> pq;
    vector<ll> dist(state_size, INFll);
    vector<int> restore(state_size, -1);

    auto dijkstra_init = [&](int i, int j, int dir) {
      if (is_available_ancillary(i, j)) {
        int state = encode_state(i, j, dir, 0);
        pq.push({0, state});
        dist[state] = 0;
        return true;
      }
      return false;
    };

    vector<int> adjacent_indices;
    if (type == MEAS_XX) {
      adjacent_indices = {0, 1};
    } else if (type == MEAS_ZZ) {
      adjacent_indices = {2, 3};
    } else {
      throw new unreachableError();
    }
    vector<pair<int, int>> full_start_adjacent;
    for (auto &&dir : adjacent_indices) {
      int di = dis[dir];
      int dj = djs[dir];
      int ni = full_start.first + di;
      int nj = full_start.second + dj;
      dijkstra_init(ni, nj, dir);
      full_start_adjacent.push_back({ni, nj});
    }

    auto parity = [&](int i, int j, int last_dir, int dir) -> int {
      bool is_corner = (last_dir <= 1) ^ (dir <= 1);
      if (!is_corner) {
        return 0;
      }

      int fi = i - dis[last_dir];
      int fj = j - djs[last_dir];
      int ni = i + dis[dir];
      int nj = j + djs[dir];

      int h1 = heights[fi][fj];
      int h2 = heights[i][j];
      int h3 = heights[ni][nj];

      int p = max(h1, h2);
      int q = max(h2, h3);

      return p != q;
    };

    vector<int> end_states;
    for (auto &&dir : adjacent_indices) {
      end_states.push_back(encode_state(full_end.first, full_end.second, dir, 0));
    }

    while (!pq.empty()) {
      auto [d, state] = pq.top();
      pq.pop();

      auto [i, j, dir, par] = decode_state(state);

      if (state == end_states[0] || state == end_states[1]) {
        break;
      }

      if (dist[state] < d || make_pair(i, j) == full_end) {
        continue;
      }

      for (int ndir = 0; ndir < 4; ndir++) {
        int di = dis[ndir];
        int dj = djs[ndir];
        int ni = i + di;
        int nj = j + dj;
        if (is_available_ancillary(ni, nj) || make_pair(ni, nj) == full_end) {
          ll nd = dist[state] + cost_func(heights[i][j], heights[ni][nj]);
          int npar = par ^ parity(i, j, dir, ndir);
          int n_state = encode_state(ni, nj, ndir, npar);
          if (dist[n_state] > nd) {
            dist[n_state] = nd;
            restore[n_state] = state;
            pq.push({nd, n_state});
          }
        }
      }
    }

    int end_state = -1;
    ll dist_adjacent = INFll;
    for (auto &&state : end_states) {
      if (dist_adjacent > dist[state]) {
        dist_adjacent = dist[state];
        end_state = state;
      }
    }

    assert(dist_adjacent < INFll);

    int cur_state = end_state;
    vector<pair<int, int>> path;
    while (true) {
      assert(cur_state >= 0);
      auto [i, j, dir, par] = decode_state(cur_state);
      pair<int, int> full_cur = {i, j};
      path.push_back(full_cur);
      if (full_cur == full_start_adjacent[0] || full_cur == full_start_adjacent[1]) {
        break;
      }
      cur_state = restore[cur_state];
    }
    path.push_back(full_start);
    reverse(path.begin(), path.end());

    if (set(path.begin(), path.end()).size() != path.size()) {
      cout << (*this) << endl;
      for (int i = 0; i < int(path.size()); i++) {
        cout << path[i].first << " " << path[i].second << endl;
      }
      cout << endl;
      assert(false);
    }

    return path;
  }

  void lift_2d_path(const vector<pair<int, int>> &path, bool kink_align = false) {
    ++path_index;

    vector<int> path_height(path.size());
    for (int index = 0; index < int(path.size()); index++) {
      auto [i, j] = path[index];
      path_height[index] = heights[i][j];
    }

    if (kink_align) {
      // It aligns kinks while the number of kinks becomes even.
      // Note that aligning may decrease the number of kinks by two.
      while (true) {
        vector<int> kinks;
        vector<int> align_cost;

        for (int i = 1; i < int(path.size()) - 1; i++) {
          auto prv = path[i - 1];
          auto cur = path[i];
          auto nxt = path[i + 1];

          int dot = (prv.first - cur.first) * (nxt.first - cur.first) +
                    (prv.second - cur.second) * (nxt.second - cur.second);
          if (dot == 0) {
            int h1 = path_height[i - 1];
            int h2 = path_height[i];
            int h3 = path_height[i + 1];

            int p = max(h1, h2);
            int q = max(h2, h3);

            if (p != q) {
              kinks.push_back(i);
              align_cost.push_back(abs(h1 - h3));
            }
          }
        }

        if (kinks.size() % 2) {
          auto min_idx =
              min_element(align_cost.begin(), align_cost.end()) - align_cost.begin();
          auto kink_idx = kinks[min_idx];
          auto &h1 = path_height[kink_idx - 1];
          auto &h2 = path_height[kink_idx];
          auto &h3 = path_height[kink_idx + 1];
          h1 = h2 = h3 = max({h1, h2, h3});
        } else {
          break;
        }
      }
    }

    vector<int> padded_path_height(path.size() + 2);
    for (int index_delta = 0; index_delta < 3; index_delta++) {
      for (int index = 0; index < int(path.size()); index++) {
        padded_path_height[index + index_delta] =
            max(padded_path_height[index + index_delta], path_height[index]);
      }
    }
    padded_path_height[0] = padded_path_height[1];
    padded_path_height[padded_path_height.size() - 1] =
        padded_path_height[padded_path_height.size() - 2];

    bool stack_flag = false;
    for (int index = 1; index < int(padded_path_height.size()) - 1; index++) {
      auto [i, j] = path[index - 1];
      int left_height = padded_path_height[index - 1];
      int middle_height = padded_path_height[index];
      int right_height = padded_path_height[index + 1];

      stacked_lattice[middle_height][i][j] = path_index;
      for (int height = min(left_height, right_height); height < middle_height;
           height++) {
        stacked_lattice[height][i][j] = path_index;
      }

      heights[i][j] = middle_height + 1;
      if (heights[i][j] == code_beats) {
        stack_flag = true;
      }
    }
    if (stack_flag) {
      _stack_lattice();
    }
  }

  double consume_instructions(bool verbose, UNITE_CALLBACK_TYPE_PJ cb_type) {
    return _consume_instructions(verbose, cb_type);
  }

  double consume_instructions_satisfying_condition(bool verbose) {
    return _consume_instructions(verbose, DIJKSTRA_PJ_LAYER_EXP_COST, true);
  }

  double consume_instructions_by_bfs_pj(bool verbose = true) {
    return _consume_instructions(verbose, BFS_PJ);
  }

  double consume_instructions_dijkstra_exp_custom_factor(bool verbose, double factor) {
    assert(factor <= 1);
    _init_members();

    auto cost_func = [&](int h, int nh) -> ll {
      int exponent = (code_beats - max(h, nh));
      int cost = INF * pow(factor, exponent);
      return max(1, cost);
    };

    auto find_2d_path = [&](two_qubit_instruction inst) -> vector<pair<int, int>> {
      return find_2d_path_dijkstra(inst, cost_func);
    };

    progress p("PJ custom ");
    p.show();

    int inst_size = instructions.size();
    for (int i = 0; i < inst_size; i++) {
      auto inst = instructions[i];
      if (verbose) {
        cerr << inst << endl;
      }
      auto path = find_2d_path(inst);
      lift_2d_path(path);
      // if (verbose) {
      //     cerr << (*this) << endl;
      // }

      p.update(100.0 * i / inst_size);
    }
    code_beats--;
    stacked_lattice.pop_back();

    p.update(100);

    if (verbose) {
      cerr << (*this) << endl;
    }

    double through_put = (double)instructions.size() / code_beats;
    if (verbose) {
      cerr << "Through Put: " << instructions.size() << "/" << code_beats << " = "
           << through_put << endl;
    }
    return through_put;
  }

  void output_mpl(int mod = 8) {
    for (int t = 0; t < code_beats; t++) {
      qubit_plane::output_mpl(cout, stacked_lattice[t], mod);
      cout << '\n';
    }
  }

  friend ostream &operator<<(ostream &os, lattice_surgery_pj &ls_pj) {
    for (int t = 0; t < ls_pj.code_beats; t++) {
      ls_pj.output_index(os, ls_pj.stacked_lattice[t]);
      os << '\n';
    }
    return os;
  }

  int code_beats;

 private:
  int path_index;

  vector<vector<vector<int>>> stacked_lattice;
  vector<vector<int>> heights;

  void _init_members() {
    path_index = 0;
    code_beats = 1;
    stacked_lattice = vector<vector<vector<int>>>(
        code_beats, vector<vector<int>>(full_qubit_size, vector<int>(full_qubit_size)));
    heights = vector<vector<int>>(full_qubit_size, vector<int>(full_qubit_size));
  }

  void _stack_lattice() {
    code_beats++;
    stacked_lattice.push_back(
        vector<vector<int>>(full_qubit_size, vector<int>(full_qubit_size)));
  }

  double _consume_instructions(bool verbose, UNITE_CALLBACK_TYPE_PJ cb_type,
                               bool kink_align = false) {
    _init_members();

    auto find_2d_path = [&](two_qubit_instruction inst) -> vector<pair<int, int>> {
      if (cb_type == BFS_PJ) {
        return find_2d_path_bfs(inst);
      } else if (cb_type == DIJKSTRA_PJ_BFS) {
        return find_2d_path_dijkstra(inst, [](int h, int nh) -> ll { return INF; });
      } else if (cb_type == DIJKSTRA_PJ_LAYER_BASED_COST) {
        return find_2d_path_dijkstra(
            inst, [](int h, int nh) -> ll { return max(h, nh) + 1; });
      } else if (cb_type == DIJKSTRA_PJ_LAYER_EXP_COST) {
        return find_2d_path_dijkstra(inst, [&](int h, int nh) -> ll {
          int shift = min((code_beats - max(h, nh)), 29);
          return INF >> shift;
        });
      } else {
        throw new unreachableError();
      }
    };

    progress p(string("PJ ") + to_string(cb_type));
    p.show();

    int inst_size = instructions.size();
    for (int i = 0; i < inst_size; i++) {
      auto inst = instructions[i];
      if (verbose) {
        cerr << inst << endl;
      }
      auto path = find_2d_path(inst);
      lift_2d_path(path, kink_align);
      // if (verbose) {
      //     cerr << (*this) << endl;
      // }

      p.update(100.0 * i / inst_size);
    }
    code_beats--;
    stacked_lattice.pop_back();

    p.update(100);

    if (verbose) {
      cerr << (*this) << endl;
    }

    double through_put = (double)instructions.size() / code_beats;
    // if (verbose) {
    cerr << "Through Put: " << instructions.size() << "/" << code_beats << " = "
         << through_put << endl;
    // }
    return through_put;
  }
};

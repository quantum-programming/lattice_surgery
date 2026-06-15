#include "lattice_surgery.hpp"

using namespace std;

int main() {
  int _w, _h, _n;
  cin >> _w >> _h >> _n;
  int main_qubit_size = int(sqrt(_n));
  assert(_n == main_qubit_size * main_qubit_size);
  assert(_w == 2 * main_qubit_size + 1);
  assert(_h == 2 * main_qubit_size + 1);

  for (int i = 0; i < _n; i++) {
    int x, y;
    cin >> x >> y;
    assert(x == 2 * (i % main_qubit_size) + 1 + 1);
    assert(y == 2 * (i / main_qubit_size) + 1 + 1);
  }

  lattice_surgery_pj ls(main_qubit_size);

  int _m;
  cin >> _m;
  std::vector<two_qubit_instruction> instructions;
  for (int _ = 0; _ < _m; _++) {
    int _t;
    cin >> _t;
    assert(_t == 2);
    int _targetId1, _targetId2;
    char _direction1, _direction2;
    cin >> _targetId1 >> _targetId2 >> _direction1 >> _direction2;
    _targetId1--;
    _targetId2--;
    assert(0 <= _targetId1 && _targetId1 < _n);
    assert(0 <= _targetId2 && _targetId2 < _n);
    assert(_direction1 == _direction2);
    assert(_direction1 == 'H' || _direction1 == 'V');
    instructions.push_back(
        {(_direction1 == 'H') ? MEAS_ZZ : MEAS_XX, _targetId1, _targetId2});
  }

  ls.assign_instructions(instructions);

  ls.consume_instructions_satisfying_condition(false);

  ls.output_mpl();

  cout << "Score:" << ls.code_beats << endl;

  return 0;
}
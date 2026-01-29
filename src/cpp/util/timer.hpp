#pragma once

#include <cassert>
#include <chrono>

struct Timer {
  using C = std::chrono::system_clock;
  Timer() {}
  void start() {
    s = C::now();
    assert(!b);
    b = 1;
  }
  void stop() {
    sum += duration();
    assert(b);
    b = 0;
  }
  void reset() { sum = 0; }
  double sec() { return sum + (b ? duration() : 0); }

 private:
  C::time_point s;
  bool b = 0;
  double sum = 0;
  double duration() {
    return std::chrono::duration<double>(C::now() - s).count();
  }
} timer, timer1, timer2, timer3;

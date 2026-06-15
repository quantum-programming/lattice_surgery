#pragma once

#include <iostream>
#include <string>

using namespace std;

#if (defined(MYPROGRESS) || defined(LOCAL)) && !defined(DISABLEMYPROGRESS)

struct progress {
 public:
  string name;
  bool first = true;

  explicit progress() : name("") {}
  explicit progress(string task_name) : name(task_name) {}

  void show() {
    string output;
    if (first) {
      first = false;
    } else {
      output += "\033[0A";
      output += "\033[2K";
    }
    if (name.length()) {
      output += name;
      output += ": ";
    }
    output += to_string(current_percent);
    output += "%";
    cerr << output << endl;
  }

  void update(int percent) {
    if (current_percent != percent) {
      update_and_show(percent);
    }
  }

 private:
  int current_percent = 0;

  void update_and_show(int percent) {
    current_percent = percent;
    show();
  }
};

#else

struct progress {
 public:
  explicit progress() {}
  explicit progress(string task_name) {}

  void show() {}

  void update(int percent) {}
};

#endif

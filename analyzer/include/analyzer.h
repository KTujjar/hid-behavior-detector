#pragma once

#include "event.h"

#include <unordered_map>
#include <vector>

class Analyzer {
public:
    explicit Analyzer(std::vector<Event> events);

    void rebuild_process_table();
    Features compute_features() const;

    const std::vector<Event>& events() const { return events_; }
    const std::unordered_map<int, ProcessInfo>& processes() const { return processes_; }

private:
    std::vector<Event> events_;
    std::unordered_map<int, ProcessInfo> processes_;

    static bool is_shell_comm(const std::string& c);
    static bool is_interpreter_comm(const std::string& c);
};

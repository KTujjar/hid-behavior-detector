#pragma once

#include <cstdint>
#include <string>
#include <vector>

enum class EventType { Exec, Fork, Connect, Unknown };

struct Event {
    std::int64_t ts_ns{};
    EventType type{EventType::Unknown};
    int pid{};
    int ppid{-1};
    std::string comm;
    int parent_pid{};
    int child_pid{};
    std::string parent_comm;
    std::string child_comm;
};

struct ProcessInfo {
    int pid{};
    int ppid{-1};
    std::string comm;
    std::int64_t first_seen_ts{-1};
    std::vector<int> children;
    bool connected{false};
};

struct Features {
    std::size_t total_events{};
    std::size_t exec_count{};
    std::size_t fork_count{};
    std::size_t connect_count{};
    double execs_per_second{};
    std::size_t max_exec_burst_1s{};
    double mean_gap_ns{};
    std::int64_t min_gap_ns{};
    std::int64_t max_gap_ns{};
    bool shell_seen{};
    std::int64_t first_shell_ts_ns{-1};
    std::int64_t first_connect_after_shell_ns{-1};
    int max_tree_depth{};
    std::size_t processes_with_connect{};
    bool interpreter_after_shell{};
};

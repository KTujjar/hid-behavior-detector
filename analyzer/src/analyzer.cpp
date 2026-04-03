#include "analyzer.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <queue>
#include <unordered_set>

bool Analyzer::is_shell_comm(const std::string& c) {
    static const char* shells[] = {"bash", "sh", "zsh", "dash", "fish"};
    for (const char* s : shells) {
        if (c == s) {
            return true;
        }
    }
    if (c.size() >= 5 && c.rfind("/bash") == c.size() - 5) {
        return true;
    }
    if (c.size() >= 3 && c.rfind("/sh") == c.size() - 3) {
        return true;
    }
    if (c.size() >= 4 && c.rfind("/zsh") == c.size() - 4) {
        return true;
    }
    return false;
}

bool Analyzer::is_interpreter_comm(const std::string& c) {
    static const char* names[] = {"python", "python3", "perl", "node", "curl", "wget", "ruby"};
    for (const char* s : names) {
        if (c.find(s) != std::string::npos) {
            return true;
        }
    }
    return false;
}

Analyzer::Analyzer(std::vector<Event> events) : events_(std::move(events)) {}

void Analyzer::rebuild_process_table() {
    processes_.clear();
    for (const Event& e : events_) {
        if (e.type == EventType::Fork) {
            ProcessInfo& parent = processes_[e.parent_pid];
            parent.pid = e.parent_pid;
            if (parent.first_seen_ts < 0 || e.ts_ns < parent.first_seen_ts) {
                parent.first_seen_ts = e.ts_ns;
            }
            parent.children.push_back(e.child_pid);

            ProcessInfo& child = processes_[e.child_pid];
            child.pid = e.child_pid;
            child.ppid = e.parent_pid;
            if (!e.child_comm.empty()) {
                child.comm = e.child_comm;
            }
            if (child.first_seen_ts < 0 || e.ts_ns < child.first_seen_ts) {
                child.first_seen_ts = e.ts_ns;
            }
        } else if (e.type == EventType::Exec) {
            ProcessInfo& p = processes_[e.pid];
            p.pid = e.pid;
            p.comm = e.comm;
            if (p.first_seen_ts < 0 || e.ts_ns < p.first_seen_ts) {
                p.first_seen_ts = e.ts_ns;
            }
        } else if (e.type == EventType::Connect) {
            ProcessInfo& p = processes_[e.pid];
            p.pid = e.pid;
            if (p.comm.empty()) {
                p.comm = e.comm;
            }
            p.connected = true;
            if (p.first_seen_ts < 0 || e.ts_ns < p.first_seen_ts) {
                p.first_seen_ts = e.ts_ns;
            }
        }
    }
}

Features Analyzer::compute_features() const {
    Features f{};
    f.total_events = events_.size();
    std::vector<std::int64_t> exec_ts;
    std::int64_t first_shell_ts = -1;
    std::int64_t first_connect_after_shell = -1;
    std::int64_t first_hid_attach_ts = -1;
    std::int64_t first_shell_after_hid_attach = -1;

    for (const Event& e : events_) {
        if (e.type == EventType::Exec) {
            ++f.exec_count;
            exec_ts.push_back(e.ts_ns);
            if (is_shell_comm(e.comm)) {
                f.shell_seen = true;
                if (first_shell_ts < 0 || e.ts_ns < first_shell_ts) {
                    first_shell_ts = e.ts_ns;
                }
            }
        } else if (e.type == EventType::Fork) {
            ++f.fork_count;
        } else if (e.type == EventType::Connect) {
            ++f.connect_count;
        } else if (e.type == EventType::HidAttach && e.action == "add") {
            ++f.hid_attach_count;
            if (first_hid_attach_ts < 0 || e.ts_ns < first_hid_attach_ts) {
                first_hid_attach_ts = e.ts_ns;
            }
            if (e.keyboard) {
                ++f.keyboard_attach_count;
                if (!e.trusted) {
                    ++f.untrusted_keyboard_attach_count;
                }
            }
        }
    }

    std::unordered_set<int> pid_connected;
    for (const Event& e : events_) {
        if (e.type == EventType::Connect) {
            pid_connected.insert(e.pid);
        }
    }
    f.processes_with_connect = pid_connected.size();

    if (!events_.empty()) {
        const std::int64_t t0 = events_.front().ts_ns;
        const std::int64_t t1 = events_.back().ts_ns;
        const double span_s = std::max(1e-9, static_cast<double>(t1 - t0) / 1e9);
        f.execs_per_second = static_cast<double>(f.exec_count) / span_s;
    }

    if (!exec_ts.empty()) {
        std::size_t j = 0;
        for (std::size_t i = 0; i < exec_ts.size(); ++i) {
            while (j < exec_ts.size() && exec_ts[j] - exec_ts[i] <= 1000000000LL) {
                ++j;
            }
            f.max_exec_burst_1s = std::max(f.max_exec_burst_1s, j - i);
        }
    }

    std::int64_t sum_gap = 0;
    int gap_count = 0;
    f.min_gap_ns = -1;
    f.max_gap_ns = -1;
    for (std::size_t i = 1; i < events_.size(); ++i) {
        const std::int64_t g = events_[i].ts_ns - events_[i - 1].ts_ns;
        if (g < 0) {
            continue;
        }
        sum_gap += g;
        ++gap_count;
        if (f.min_gap_ns < 0 || g < f.min_gap_ns) {
            f.min_gap_ns = g;
        }
        if (f.max_gap_ns < 0 || g > f.max_gap_ns) {
            f.max_gap_ns = g;
        }
    }
    if (gap_count > 0) {
        f.mean_gap_ns = static_cast<double>(sum_gap) / static_cast<double>(gap_count);
    }

    f.first_shell_ts_ns = first_shell_ts;
    if (first_shell_ts >= 0) {
        for (const Event& e : events_) {
            if (e.type != EventType::Connect) {
                continue;
            }
            if (e.ts_ns <= first_shell_ts) {
                continue;
            }
            const std::int64_t delta = e.ts_ns - first_shell_ts;
            if (first_connect_after_shell < 0 || delta < first_connect_after_shell) {
                first_connect_after_shell = delta;
            }
        }
    }
    f.first_connect_after_shell_ns = first_connect_after_shell;
    f.first_hid_attach_ts_ns = first_hid_attach_ts;
    if (first_hid_attach_ts >= 0) {
        for (const Event& e : events_) {
            if (e.type != EventType::Exec || !is_shell_comm(e.comm) || e.ts_ns < first_hid_attach_ts) {
                continue;
            }
            const std::int64_t delta = e.ts_ns - first_hid_attach_ts;
            if (first_shell_after_hid_attach < 0 || delta < first_shell_after_hid_attach) {
                first_shell_after_hid_attach = delta;
            }
        }
    }
    f.first_shell_after_hid_attach_ns = first_shell_after_hid_attach;

    std::unordered_set<int> child_pids;
    std::unordered_map<int, std::vector<int>> children;
    for (const Event& e : events_) {
        if (e.type != EventType::Fork) {
            continue;
        }
        children[e.parent_pid].push_back(e.child_pid);
        child_pids.insert(e.child_pid);
    }
    std::vector<int> roots;
    for (const auto& kv : children) {
        if (child_pids.find(kv.first) == child_pids.end()) {
            roots.push_back(kv.first);
        }
    }
    if (roots.empty()) {
        for (const auto& kv : children) {
            roots.push_back(kv.first);
        }
    }
    int max_depth = 0;
    for (int r : roots) {
        std::queue<std::pair<int, int>> q;
        q.push({r, 1});
        while (!q.empty()) {
            auto cur = q.front();
            q.pop();
            max_depth = std::max(max_depth, cur.second);
            auto it = children.find(cur.first);
            if (it == children.end()) {
                continue;
            }
            for (int ch : it->second) {
                q.push({ch, cur.second + 1});
            }
        }
    }
    f.max_tree_depth = max_depth;

    constexpr std::int64_t kPairWindow = 500000000LL;
    for (std::size_t i = 1; i < events_.size(); ++i) {
        const Event& a = events_[i - 1];
        const Event& b = events_[i];
        if (a.type != EventType::Exec || b.type != EventType::Exec) {
            continue;
        }
        if (b.ts_ns - a.ts_ns > kPairWindow) {
            continue;
        }
        if (is_shell_comm(a.comm) && is_interpreter_comm(b.comm)) {
            f.interpreter_after_shell = true;
            break;
        }
    }

    return f;
}

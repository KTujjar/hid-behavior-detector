#include "parser.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <sstream>

namespace {

std::string trim(const std::string& s) {
    std::size_t a = 0;
    while (a < s.size() && std::isspace(static_cast<unsigned char>(s[a]))) {
        ++a;
    }
    std::size_t b = s.size();
    while (b > a && std::isspace(static_cast<unsigned char>(s[b - 1]))) {
        --b;
    }
    return s.substr(a, b - a);
}

bool extract_json_string(const std::string& line, const char* key, std::string& out) {
    const std::string needle = std::string("\"") + key + "\":\"";
    auto pos = line.find(needle);
    if (pos == std::string::npos) {
        return false;
    }
    pos += needle.size();
    std::size_t end = pos;
    while (end < line.size()) {
        if (line[end] == '\\' && end + 1 < line.size()) {
            end += 2;
            continue;
        }
        if (line[end] == '"') {
            break;
        }
        ++end;
    }
    if (end >= line.size()) {
        return false;
    }
    out = line.substr(pos, end - pos);
    return true;
}

std::int64_t extract_ll(const std::string& line, const char* key) {
    const std::string needle = std::string("\"") + key + "\":";
    auto pos = line.find(needle);
    if (pos == std::string::npos) {
        return 0;
    }
    pos += needle.size();
    while (pos < line.size() && (line[pos] == ' ' || line[pos] == '\t')) {
        ++pos;
    }
    std::size_t end = pos;
    if (pos < line.size() && (line[pos] == '-' || std::isdigit(static_cast<unsigned char>(line[pos])))) {
        ++end;
        while (end < line.size() && std::isdigit(static_cast<unsigned char>(line[end]))) {
            ++end;
        }
    }
    if (end == pos) {
        return 0;
    }
    return std::stoll(line.substr(pos, end - pos));
}

int extract_int(const std::string& line, const char* key) {
    return static_cast<int>(extract_ll(line, key));
}

Event parse_line(const std::string& raw) {
    const std::string line = trim(raw);
    if (line.empty() || line[0] != '{') {
        return {};
    }
    Event e;
    e.ts_ns = extract_ll(line, "ts_ns");
    std::string type;
    if (!extract_json_string(line, "type", type)) {
        const auto tpos = line.find("\"type\":");
        if (tpos != std::string::npos) {
            auto q = line.find('"', tpos + 7);
            if (q != std::string::npos) {
                auto q2 = line.find('"', q + 1);
                if (q2 != std::string::npos) {
                    type = line.substr(q + 1, q2 - q - 1);
                }
            }
        }
    }
    if (type == "exec") {
        e.type = EventType::Exec;
        e.pid = extract_int(line, "pid");
        extract_json_string(line, "comm", e.comm);
    } else if (type == "fork") {
        e.type = EventType::Fork;
        e.parent_pid = extract_int(line, "parent_pid");
        e.child_pid = extract_int(line, "child_pid");
        extract_json_string(line, "parent_comm", e.parent_comm);
        extract_json_string(line, "child_comm", e.child_comm);
    } else if (type == "connect") {
        e.type = EventType::Connect;
        e.pid = extract_int(line, "pid");
        extract_json_string(line, "comm", e.comm);
    } else {
        e.type = EventType::Unknown;
    }
    return e;
}

}  // namespace

std::vector<Event> load_events_from_file(const std::string& path) {
    std::ifstream in(path);
    if (!in) {
        return {};
    }
    std::vector<Event> out;
    std::string line;
    while (std::getline(in, line)) {
        Event e = parse_line(line);
        if (e.type == EventType::Exec || e.type == EventType::Fork || e.type == EventType::Connect) {
            out.push_back(e);
        }
    }
    return out;
}

std::vector<Event> load_events_from_files(const std::vector<std::string>& paths) {
    std::vector<Event> all;
    for (const auto& p : paths) {
        auto chunk = load_events_from_file(p);
        all.insert(all.end(), chunk.begin(), chunk.end());
    }
    return all;
}

void sort_events_by_time(std::vector<Event>& events) {
    std::sort(events.begin(), events.end(), [](const Event& a, const Event& b) {
        if (a.ts_ns != b.ts_ns) {
            return a.ts_ns < b.ts_ns;
        }
        return static_cast<int>(a.type) < static_cast<int>(b.type);
    });
}

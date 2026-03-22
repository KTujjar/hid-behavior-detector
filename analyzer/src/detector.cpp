#include "detector.h"

#include <sstream>

namespace {

constexpr int kThreshold = 7;

void add_reason(std::vector<std::string>& reasons, int& score, int delta, std::string text) {
    score += delta;
    std::ostringstream os;
    os << "(" << (delta >= 0 ? "+" : "") << delta << ") " << text;
    reasons.push_back(os.str());
}

}  // namespace

DetectionResult detect(const Features& f) {
    DetectionResult r;
    r.score = 0;

    if (f.shell_seen) {
        add_reason(r.reasons, r.score, 3, "shell-related exec observed");
    }
    if (f.max_exec_burst_1s >= 5) {
        std::ostringstream os;
        os << "high exec burst: max " << f.max_exec_burst_1s << " execs within 1 second window";
        add_reason(r.reasons, r.score, 2, os.str());
    }
    if (f.first_shell_ts_ns >= 0 && f.first_connect_after_shell_ns >= 0 &&
        f.first_connect_after_shell_ns <= 2000000000LL) {
        const double ms = static_cast<double>(f.first_connect_after_shell_ns) / 1e6;
        std::ostringstream os;
        os << "network connect within ~" << static_cast<int>(ms + 0.5) << " ms after first shell exec";
        add_reason(r.reasons, r.score, 3, os.str());
    }
    if (f.max_tree_depth > 3) {
        std::ostringstream os;
        os << "process tree depth " << f.max_tree_depth << " (threshold 3)";
        add_reason(r.reasons, r.score, 1, os.str());
    }
    if (f.interpreter_after_shell) {
        add_reason(r.reasons, r.score, 2,
                   "interpreter/network tool exec shortly after shell-like exec");
    }

    r.suspicious = r.score >= kThreshold;
    return r;
}

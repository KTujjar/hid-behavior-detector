#include "report.h"

#include <fstream>
#include <iomanip>
#include <sstream>

std::string format_report(const std::string& run_label,
                          const Features& f,
                          const DetectionResult& d) {
    std::ostringstream os;
    os << "Run: " << run_label << "\n";
    os << "---\n";
    os << "Total events:     " << f.total_events << "\n";
    os << "Exec events:      " << f.exec_count << "\n";
    os << "Fork events:      " << f.fork_count << "\n";
    os << "Connect events:   " << f.connect_count << "\n";
    os << "Execs / second:   " << std::fixed << std::setprecision(3) << f.execs_per_second << "\n";
    os << "Max exec burst (1s window): " << f.max_exec_burst_1s << "\n";
    os << "Mean event gap (ns): " << std::fixed << std::setprecision(3) << f.mean_gap_ns << "\n";
    if (f.min_gap_ns >= 0) {
        os << "Min gap (ns): " << f.min_gap_ns << "\n";
    }
    if (f.max_gap_ns >= 0) {
        os << "Max gap (ns): " << f.max_gap_ns << "\n";
    }
    os << "Max tree depth:   " << f.max_tree_depth << "\n";
    os << "PIDs w/ connect:  " << f.processes_with_connect << "\n";
    os << "Shell seen:       " << (f.shell_seen ? "yes" : "no") << "\n";
    os << "---\n";
    os << "Suspicion score:  " << d.score << "\n";
    os << "Suspicious:       " << (d.suspicious ? "yes" : "no") << "\n";
    os << "Reasons:\n";
    for (const auto& line : d.reasons) {
        os << "  - " << line << "\n";
    }
    return os.str();
}

bool write_report_file(const std::string& path,
                       const std::string& run_label,
                       const Features& f,
                       const DetectionResult& d) {
    std::ofstream out(path);
    if (!out) {
        return false;
    }
    out << format_report(run_label, f, d);
    return true;
}

#include "analyzer.h"
#include "detector.h"
#include "parser.h"
#include "report.h"

#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

static void print_usage() {
    std::cerr << "Usage:\n"
              << "  hid-analyzer <input.jsonl> [more.jsonl ...]\n"
              << "  hid-analyzer --merge exec.jsonl fork.jsonl connect.jsonl\n"
              << "  hid-analyzer --out <report.txt> <input.jsonl> [...]\n";
}

static std::string default_report_path(const std::string& input_path) {
    auto pos = input_path.find_last_of("/\\");
    std::string base = (pos == std::string::npos) ? input_path : input_path.substr(pos + 1);
    std::string stem = base;
    auto dot = stem.find_last_of('.');
    if (dot != std::string::npos) {
        stem = stem.substr(0, dot);
    }
    return std::string("results/") + stem + "_report.txt";
}

int main(int argc, char** argv) {
    if (argc < 2) {
        print_usage();
        return 1;
    }

    std::vector<std::string> inputs;
    std::string out_path;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--out" && i + 1 < argc) {
            out_path = argv[++i];
        } else if (a == "-h" || a == "--help") {
            print_usage();
            return 0;
        } else {
            inputs.push_back(a);
        }
    }

    if (inputs.empty()) {
        print_usage();
        return 1;
    }

    std::vector<Event> events = load_events_from_files(inputs);
    sort_events_by_time(events);

    Analyzer analyzer(std::move(events));
    analyzer.rebuild_process_table();
    Features f = analyzer.compute_features();
    DetectionResult d = detect(f);

    std::string label = inputs.size() == 1 ? inputs[0] : "merged";

    const std::string text = format_report(label, f, d);
    std::cout << text;
    std::cout.flush();

    if (out_path.empty()) {
        out_path = default_report_path(inputs[0]);
    }
    {
        std::error_code ec;
        std::filesystem::path p(out_path);
        if (p.has_parent_path()) {
            std::filesystem::create_directories(p.parent_path(), ec);
        }
    }
    if (write_report_file(out_path, label, f, d)) {
        std::cerr << "\nReport written to: " << out_path << "\n";
    } else {
        std::cerr << "\nWarning: could not write report to " << out_path << "\n";
        return 1;
    }

    return 0;
}

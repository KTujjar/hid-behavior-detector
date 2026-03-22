#pragma once

#include "detector.h"
#include "event.h"

#include <string>

std::string format_report(const std::string& run_label,
                          const Features& f,
                          const DetectionResult& d);

bool write_report_file(const std::string& path,
                       const std::string& run_label,
                       const Features& f,
                       const DetectionResult& d);

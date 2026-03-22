#pragma once

#include "event.h"

#include <string>
#include <vector>

struct DetectionResult {
    int score{};
    bool suspicious{};
    std::vector<std::string> reasons;
};

DetectionResult detect(const Features& f);

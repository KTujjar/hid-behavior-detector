#pragma once

#include "event.h"

#include <string>
#include <vector>

std::vector<Event> load_events_from_file(const std::string& path);
std::vector<Event> load_events_from_files(const std::vector<std::string>& paths);
void sort_events_by_time(std::vector<Event>& events);

cmake_minimum_required(VERSION 3.16)
project(hid-behavior-analyzer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(hid-analyzer
    src/main.cpp
    src/event.cpp
    src/parser.cpp
    src/analyzer.cpp
    src/detector.cpp
    src/report.cpp
)

target_include_directories(hid-analyzer PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/include")

if(MSVC)
    target_compile_options(hid-analyzer PRIVATE /W4 /permissive-)
else()
    target_compile_options(hid-analyzer PRIVATE -Wall -Wextra -Wpedantic)
endif()

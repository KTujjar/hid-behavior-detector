#!/usr/bin/env bash
# Build the C++ analyzer, then start the Tk desktop UI.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

ANALYZER_DIR="$PROJECT_ROOT/analyzer"
BUILD_DIR="$ANALYZER_DIR/build"

echo "Building analyzer (cmake)..."
cmake -S "$ANALYZER_DIR" -B "$BUILD_DIR"
cmake --build "$BUILD_DIR"

echo "Starting desktop app..."
exec python3 "$PROJECT_ROOT/ui/desktop_app.py"

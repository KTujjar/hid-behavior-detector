#!/usr/bin/env bash
# Reads results/summary.tsv (from batch_analyze.sh) and prints TP/TN/FP/FN counts.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SUMMARY="${1:-$PROJECT_ROOT/results/summary.tsv}"

if [[ ! -f "$SUMMARY" ]]; then
  echo "No summary file: $SUMMARY"
  echo "Run scripts/batch_analyze.sh first."
  exit 1
fi

awk -F'\t' 'NR==1{next}
{
  type=$2; fl=$4;
  if (type=="normal" && fl=="no") tn++;
  else if (type=="normal" && fl=="yes") fp++;
  else if (type=="scripted" && fl=="yes") tp++;
  else if (type=="scripted" && fl=="no") fn++;
}
END{
  print "True positives (scripted flagged):  " tp+0
  print "True negatives (normal not flagged): " tn+0
  print "False positives (normal flagged):     " fp+0
  print "False negatives (scripted missed):     " fn+0
}' "$SUMMARY"

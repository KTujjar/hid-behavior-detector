cd /path/to/hid-behavior-detector

for t in scripts/scripted_test_*.sh; do
  echo "Running $t"
  timeout 10s bash scripts/collect_trace.sh &
  CAP_PID=$!
  sleep 2
  bash "$t"
  wait "$CAP_PID"
  sleep 1
done

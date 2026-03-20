mkdir -p data/run1
sudo bpftrace tracing/exec_trace.bt > data/run1/exec.jsonl &
EXEC_PID=$!
sudo bpftrace tracing/fork_trace.bt > data/run1/fork.jsonl &
FORK_PID=$!
sudo bpftrace tracing/connect_trace.bt > data/run1/connect.jsonl &
CONN_PID=$!

echo "Tracing started. Press Enter to stop."
read

sudo kill $EXEC_PID $FORK_PID $CONN_PID


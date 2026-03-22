#!/bin/bash

echo "burst test"
for i in {1..5}; do
    echo "iteration $i" > /dev/null
    ls > /dev/null
    pwd > /dev/null
done
python3 -c "print('loop finished')"

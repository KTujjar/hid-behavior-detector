#!/bin/bash

bash -c "echo begin"
sleep 0.1
ls > /dev/null
sleep 0.1
curl -s https://example.com > /dev/null
sleep 0.1
python3 -c "print('finished')"

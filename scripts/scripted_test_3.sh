#!/bin/bash

bash -c "echo shell started"
sleep 0.2
python3 -c "print('python ran')"
sleep 0.2
curl -s https://example.com > /dev/null
sleep 0.2
ls > /dev/null
sleep 0.2
date > /dev/null

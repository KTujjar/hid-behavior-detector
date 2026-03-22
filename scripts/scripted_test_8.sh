#!/bin/bash

echo "starting heavy benign burst"
bash -c "echo shell one"
python3 -c "print('python one')"
python3 -c "print('python two')"
curl -s https://example.com > /dev/null
uname -a > /dev/null
id > /dev/null
date > /dev/null
echo "complete"

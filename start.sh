#!/bin/bash
nohup python -u src/main.py >> log/main.log 2>&1 &
echo $! > main.pid
#!/bin/bash
# cap.sh <name> [settle]  - screenshot to /home/claude/shots/<name>.png
python3 "$(dirname "$0")/kodictl.py" shot "/home/claude/shots/$1.png" "${2:-1.5}" >/dev/null && echo "shot $1"

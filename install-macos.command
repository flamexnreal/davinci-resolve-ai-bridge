#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 install.py
printf "\nPress Return to close..."
read answer
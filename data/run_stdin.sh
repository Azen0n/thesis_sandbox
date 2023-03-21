#!/bin/bash

echo -e "$2" > code.py

input=${1//,/\\n}

echo -e "$input" | python code.py > output.txt 2> error.txt

if [ -z "$(cat error.txt)" ]; then
  echo "[OUTPUT]"
  cat output.txt
else
  echo "[ERROR]"
  cat error.txt
fi
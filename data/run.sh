#!/bin/bash

echo -e "$1" > tests.txt
echo -e "$2" > code.py

while read -r input
do
  read -r output
  input=${input//,/\\n}

  echo -e "$input" | python code.py > output.txt 2> error.txt
  code_output="$(cat output.txt)"

  if [ -z "${code_output}" ]; then
    echo "[ERROR] input: $input  output: $output  code_output: $code_output"
    cat error.txt
    break
  fi

  if [[ "$code_output" != "$output" ]]; then
    echo "[FAILED] input: $input  output: $output  code_output: $code_output"
    break
  fi

  echo "[PASSED] input: $input  output: $output  code_output: $code_output"

done < tests.txt

#!/usr/bin/env bash

# Check if user provided a valid argument
if [ "$#" -ne 1 ]; then
	printf "Use only 1 parameter, the input absolute file path.\n Exiting..."
	exit 1
fi


input_file="$1"

sed -E 's/(nsec)([0-9ac-hj-np-z]{28})(.*)/\1**** # MODIFY ME!!!\3/g' "$input_file"

#!/bin/bash
[ -n "$1" ] || { echo "Need to provide payload"; exit 1; }
cl /commands -d"$1" | tee /tmp/last | jq

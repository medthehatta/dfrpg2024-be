#!/bin/bash

path="$1"; shift
curl -w"\n" "http://localhost:6501/$path" "$@"


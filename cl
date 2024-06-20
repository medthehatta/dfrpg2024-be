#!/bin/bash

path="$1"; shift
curl -w"\n" "http://localhost:8000/$path" "$@"


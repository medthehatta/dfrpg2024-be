#!/bin/bash

cl "$@" | tee /tmp/last | jq

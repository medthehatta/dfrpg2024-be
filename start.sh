#!/bin/bash
while true
do
    [[ -n "$(git status --porcelain)" ]] || { git fetch origin main && git reset --hard FETCH_HEAD; }
    docker-compose up --build
done

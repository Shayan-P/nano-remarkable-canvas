#!/usr/bin/env bash
REMARKABLE_IP=${REMARKABLE_IP:-192.168.1.89}

echo "Using reMarkable IP: $REMARKABLE_IP"

cd "$(dirname "$0")"

echo "Starting stroke-convertor and receiver..."
ssh root@$REMARKABLE_IP "cat /dev/input/event1" | uv run python stroke-convertor.py | uv run python receiver.py

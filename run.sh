#!/usr/bin/env bash
REMARKABLE_IP=192.168.1.89

cd "$(dirname "$0")"
ssh root@$REMARKABLE_IP "cat /dev/input/event1" | uv run python stroke-convertor.py | uv run python receiver.py

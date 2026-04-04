#!/bin/bash
# Run TeslaBar from the virtual environment
cd "$(dirname "$0")"
source .venv/bin/activate
python -m teslabar

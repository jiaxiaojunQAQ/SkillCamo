#!/bin/bash
# HPR-LP Solver Script
# Usage: hprlp_solve.sh <mps_file> [time_limit] [stoptol] [device]

MPS_FILE=$1
TIME_LIMIT=${2:-3600}
STOP_TOL=${3:-1e-6}
DEVICE=${4:--1}

JULIA=/home/ljw/julia/julia-1.10.4/bin/julia
PROJECT=/home/ljw/.openclaw/workspace/HPR-LP
SCRIPT=/home/ljw/.openclaw/workspace/HPR-LP/hprlp_solve.jl

if [ -z "$MPS_FILE" ]; then
    echo "Usage: $0 <mps_file> [time_limit] [stoptol] [device]"
    echo "  time_limit: default 3600 seconds"
    echo "  stoptol: default 1e-6"
    echo "  device: default -1 (CPU), use 0 for GPU"
    exit 1
fi

$JULIA --project=$PROJECT $SCRIPT $MPS_FILE $TIME_LIMIT $STOP_TOL $DEVICE

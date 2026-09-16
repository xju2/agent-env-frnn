#!/usr/bin/env bash
set -euo pipefail

checkpoint="${FRNN_CHECKPOINT:-/opt/frnn-checkpoint}"
workspace="${FRNN_WORKSPACE:-/workspace/libFRNN}"

mkdir -p "${workspace}"
if [[ -z "$(find "${workspace}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    cp -a "${checkpoint}/." "${workspace}/"
fi

if [[ ! -d "${workspace}/.git" ]]; then
    python3 /opt/frnn-harness/scripts/verify_snapshot.py --root "${workspace}"
    git -C "${workspace}" init --quiet
    git -C "${workspace}" config user.name "FRNN experiment baseline"
    git -C "${workspace}" config user.email "frnn-experiment@invalid.example"
    git -C "${workspace}" add --all
    git -C "${workspace}" commit --quiet -m "Baseline libFRNN ${FRNN_UPSTREAM_COMMIT}"
fi

cd "${workspace}"
exec "$@"

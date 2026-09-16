#!/usr/bin/env bash
set -euo pipefail

command -v nvidia-smi >/dev/null || { echo "nvidia-smi is unavailable; start the container with --gpus." >&2; exit 1; }
nvidia-smi >/dev/null || { echo "The NVIDIA runtime did not expose a working GPU." >&2; exit 1; }

gpu_name="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1 | xargs)"
driver="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1 | xargs)"
compute_cap="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -n1 | xargs || true)"

echo "GPU: ${gpu_name}"
echo "Driver: ${driver}"
echo "Compute capability: ${compute_cap:-unknown}"
nvcc --version

if [[ -n "${EXPECTED_GPU_REGEX:-}" ]] && [[ ! "${gpu_name}" =~ ${EXPECTED_GPU_REGEX} ]]; then
    echo "Expected GPU matching '${EXPECTED_GPU_REGEX}', found '${gpu_name}'." >&2
    exit 1
fi
if [[ -n "${EXPECTED_COMPUTE_CAPABILITY:-}" && -n "${compute_cap}" && "${compute_cap}" != "${EXPECTED_COMPUTE_CAPABILITY}" ]]; then
    echo "Expected compute capability ${EXPECTED_COMPUTE_CAPABILITY}, found ${compute_cap}." >&2
    exit 1
fi

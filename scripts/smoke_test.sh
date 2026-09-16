#!/usr/bin/env bash
set -euo pipefail

check-frnn-gpu
build_dir="$(mktemp -d /tmp/frnn-smoke.XXXXXX)"
cleanup() { rm -rf -- "${build_dir}"; }
trap cleanup EXIT

cmake -S "${FRNN_WORKSPACE:-/workspace/libFRNN}" -B "${build_dir}" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CUDA_ARCHITECTURES="${CUDAARCHS:-75}" \
    -DFRNN_BUILD_TESTS=ON \
    -DFRNN_BUILD_BENCHMARKS=ON \
    -DFRNN_BUILD_PYTHON=ON \
    -Dpybind11_DIR="$(python3 -m pybind11 --cmakedir)"
cmake --build "${build_dir}" --parallel "${CMAKE_BUILD_PARALLEL_LEVEL:-8}"
ctest --test-dir "${build_dir}" --output-on-failure
echo "FRNN CUDA build and tests completed successfully."

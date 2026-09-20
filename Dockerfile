# syntax=docker/dockerfile:1.7
ARG CUDA_IMAGE=nvidia/cuda:13.0.1-devel-ubuntu22.04
FROM ${CUDA_IMAGE}

ARG DEBIAN_FRONTEND=noninteractive
ARG NODE_VERSION=22.19.0
ARG NODE_SHA256=c0649af18e6a24f6fe5535a3e86b341dd49a8e71117c8b68bde973ef834f16f2
ARG PYTORCH_VERSION=2.13.0+cu130
ARG PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu130

LABEL org.opencontainers.image.title="FRNN autonomous-agent experiment environment" \
      org.opencontainers.image.source="https://github.com/xju2/agent-env-frnn" \
      org.opencontainers.image.revision="5ce9f21e2a2f12edfc5734fdd31973098a2f8d6d"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        ccache \
        cmake \
        curl \
        cuda-nsight-compute-13-0=13.0.1-1 \
        cuda-nsight-systems-13-0=13.0.1-1 \
        fd-find \
        gdb \
        git \
        git-lfs \
        jq \
        less \
        libnuma-dev \
        lsb-release \
        ninja-build \
        numactl \
        openssh-client \
        pciutils \
        pkg-config \
        procps \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        ripgrep \
        rsync \
        time \
        unzip \
        vim-tiny \
        wget \
        xz-utils \
        zip \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/fdfind /usr/local/bin/fd

RUN curl --fail --location --silent --show-error \
        "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
        --output /tmp/node.tar.xz \
    && echo "${NODE_SHA256}  /tmp/node.tar.xz" | sha256sum --check --strict \
    && tar --extract --xz --file=/tmp/node.tar.xz --directory=/usr/local --strip-components=1 \
    && rm /tmp/node.tar.xz \
    && corepack enable

RUN python3 -m pip install --no-cache-dir \
        numpy==1.26.4 \
        pybind11==2.11.1 \
        pytest==8.3.5 \
        scikit-build-core==0.10.7 \
    && python3 -m pip install --no-cache-dir \
        --index-url "${PYTORCH_INDEX_URL}" \
        "torch==${PYTORCH_VERSION}" \
    && python3 -c "import torch; assert torch.__version__ == '${PYTORCH_VERSION}'; assert torch.version.cuda == '13.0'"

ENV CUDAARCHS=75 \
    EXPECTED_CUDA_VERSION=13.0 \
    EXPECTED_PYTORCH_VERSION=2.13.0+cu130 \
    CMAKE_BUILD_PARALLEL_LEVEL=8 \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    FRNN_UPSTREAM_COMMIT=5ce9f21e2a2f12edfc5734fdd31973098a2f8d6d \
    FRNN_HARNESS=/opt/frnn-harness \
    FRNN_CHECKPOINT=/opt/frnn-checkpoint \
    FRNN_WORKSPACE=/workspace/libFRNN

COPY workspace/ /opt/frnn-checkpoint/
COPY upstream/ /opt/frnn-harness/upstream/
COPY prompts/ /opt/frnn-harness/prompts/
COPY scripts/ /opt/frnn-harness/scripts/
COPY experiment/ /opt/frnn-harness/experiment/

RUN chmod +x /opt/frnn-harness/scripts/*.sh /opt/frnn-harness/scripts/*.py \
    && mkdir -p /workspace/libFRNN /runs \
    && ln -s /opt/frnn-harness/scripts/frnn-entrypoint.sh /usr/local/bin/frnn-entrypoint \
    && ln -s /opt/frnn-harness/scripts/check_gpu.sh /usr/local/bin/check-frnn-gpu \
    && ln -s /opt/frnn-harness/scripts/smoke_test.sh /usr/local/bin/smoke-test-frnn \
    && ln -s /opt/frnn-harness/scripts/run_experiment.py /usr/local/bin/run-frnn-experiment

WORKDIR /workspace/libFRNN
ENTRYPOINT ["/usr/local/bin/frnn-entrypoint"]
CMD ["bash"]

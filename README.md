# Reproducible FRNN agent environment

This repository defines the common starting point for controlled autonomous-agent optimization experiments on [libFRNN](https://github.com/xju2/libFRNN). The editable source checkpoint is an exact copy of commit [`5ce9f21e2a2f12edfc5734fdd31973098a2f8d6d`](https://github.com/xju2/libFRNN/commit/5ce9f21e2a2f12edfc5734fdd31973098a2f8d6d), stored in `workspace/`. Its Git blob identities are recorded in `upstream/source-manifest.json` and can be checked with `make verify`.

The repository deliberately separates three things:

- `workspace/`: the immutable source checkpoint copied into each fresh container workspace;
- `Dockerfile`: the common scientific build and GPU environment;
- `experiment/`, `prompts/`, and `scripts/`: the run protocol and provenance recorder.

## Step 1: build the common environment

The image uses CUDA 12.0.1 on Ubuntu 22.04, targets compute capability 7.5 (`sm_75`) for the GeForce RTX 2070, and includes CMake, Ninja, C/C++, Python, Node.js, Git, Nsight Compute, Nsight Systems, and standard diagnostic tools.

Faraday needs a compatible NVIDIA driver, Docker, and NVIDIA Container Toolkit. Build and validate the image on the designated GPU:

```bash
docker build --pull --tag agent-env-frnn:cuda12.0 .
docker run --rm --gpus '"device=0"' \
  -e EXPECTED_GPU_REGEX='RTX 2070' \
  -e EXPECTED_COMPUTE_CAPABILITY=7.5 \
  agent-env-frnn:cuda12.0 smoke-test-frnn
```

Record the immutable local image identity used by every arm (and the registry digest as well if the image is pushed):

```bash
docker image inspect agent-env-frnn:cuda12.0 --format '{{.Id}}'
```

Do not install Codex or Claude Code in this common image: the agent framework and version are treatment variables. Build one thin derived image per treatment, pin the CLI version, and retain the same base-image digest. Mount credentials at run time; never bake them into an image or commit them.

The canonical goal text is `prompts/goal.txt`. `docs/optimize_compute.md`, `docs/performance_report.md`, and `docs/optimization_log.md` are already present in the checkpoint and therefore visible to every agent.

The real-life benchmark also expects `data/embedding_data.csv` and `data/edge_list.csv`. These inputs are not in the upstream commit. Mount the same host directory read-only at `/workspace/libFRNN/data` for every run and record both SHA-256 hashes; see `data/README.md`.

## Step 2: record a run

Use one immutable directory under `runs/` per attempt. `run-frnn-experiment` creates:

- `manifest.json`: agent/model configuration, budget, container and host/GPU facts, dataset hashes, timestamps, exit state, and output Git state;
- `goal.txt`: the exact prompt shown to the agent;
- `transcript.log`: combined stdout/stderr from the autonomous process;
- `events.jsonl`: machine-readable lifecycle events;
- `result.patch`: the final diff from the clean checkpoint.

A typical invocation inside the container is:

```bash
run-frnn-experiment \
  --run-id codex-gpt-5-6-sol-medium-r1 \
  --framework Codex \
  --framework-version '<exact CLI version>' \
  --model gpt-5.6-sol \
  --model-version '<exact model snapshot, if exposed>' \
  --reasoning medium \
  --repetition 1 \
  --budget-seconds 18000 \
  --image-ref '<derived image digest>' \
  -- <noninteractive agent command and flags>
```

Anything not captured automatically—API token counts/cost, context-compaction policy, permissions, unexpected human intervention, benchmark samples, and correctness results—must be added to `manifest.json` before the record is frozen. The allowed structure is documented in `experiment/run.schema.json`; `experiment/run.template.json` is a filled example. Use `experiment/matrix.csv` as the prospective experiment plan and assign every manifest one of its unique arm IDs.

For fair comparisons:

1. Use the same base-image digest, source manifest, GPU allocation, datasets, prompt bytes, network policy, permissions, wall-clock budget, and benchmark procedure.
2. Treat framework, CLI version, model, reasoning level, and repetition as explicit factors.
3. Keep compilation and benchmark time inside the five-hour budget if that is the stated treatment.
4. Run correctness checks before accepting latency results, preserve raw samples, and benchmark all outputs again on A100 with an identical A100 protocol.
5. Never reuse an agent workspace. Start from a new container or an empty mounted workspace for every run.

Profiler access is host-controlled. Nsight Compute counter collection may require the NVIDIA driver's performance-counter permission, and Nsight Systems CPU sampling may require an appropriate `perf_event_paranoid` setting. Change those host settings only on a trusted dedicated system and record them in the run manifest.

## Repository map

| Path | Purpose |
|---|---|
| `workspace/` | Exact libFRNN checkpoint presented to agents |
| `upstream/source-manifest.json` | File-level checkpoint provenance |
| `prompts/goal.txt` | Canonical autonomous optimization goal |
| `experiment/` | Run schema, example, and protocol guidance |
| `scripts/` | Snapshot verification, GPU checks, workspace initialization, and run capture |
| `runs/` | Local run artifacts; ignored except for its placeholder |

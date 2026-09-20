#!/usr/bin/env python3
"""Run one autonomous treatment and preserve a machine-readable record."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import signal
import subprocess
import time
from typing import Any

UTC = dt.timezone.utc


def now() -> str:
    return dt.datetime.now(UTC).isoformat().replace("+00:00", "Z")


def output(argv: list[str]) -> str | None:
    try:
        return subprocess.check_output(
            argv, stderr=subprocess.STDOUT, text=True, timeout=15
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()




def capture_command_output(
    path: Path, argv: list[str], timeout: int = 120
) -> dict[str, Any]:
    """Write stdout exactly as emitted and return command diagnostics."""
    try:
        with path.open("wb") as stream:
            completed = subprocess.run(
                argv,
                stdout=stream,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout,
            )
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        return {
            "return_code": completed.returncode,
            "stderr": stderr or None,
        }
    except (OSError, subprocess.SubprocessError) as error:
        path.write_bytes(b"")
        return {"return_code": None, "stderr": str(error)}


def datasets(workspace: Path) -> list[dict[str, Any]]:
    found = []
    for name in ("embedding_data.csv", "edge_list.csv"):
        path = workspace / "data" / name
        if path.is_file():
            found.append(
                {
                    "path": f"data/{name}",
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    return found


def environment(image_ref: str | None) -> dict[str, Any]:
    gpu_query = output(
        [
            "nvidia-smi",
            "--query-gpu=name,uuid,driver_version,memory.total,compute_cap",
            "--format=csv,noheader,nounits",
        ]
    )
    paranoid = Path("/proc/sys/kernel/perf_event_paranoid")
    return {
        "image_ref": image_ref,
        "host": {
            "hostname": platform.node(),
            "kernel": platform.release(),
            "machine": platform.machine(),
            "cpu": output(
                [
                    "bash",
                    "-lc",
                    "lscpu | sed -n 's/^Model name:[[:space:]]*//p' | head -n1",
                ]
            ),
            "memory_bytes": output(
                ["bash", "-lc", "awk '/MemTotal/ {print $2 * 1024}' /proc/meminfo"]
            ),
            "perf_event_paranoid": (
                paranoid.read_text(encoding="utf-8").strip()
                if paranoid.exists()
                else None
            ),
        },
        "gpu": {
            "nvidia_smi_csv": gpu_query,
            "full_nvidia_smi": output(["nvidia-smi", "-q"]),
        },
        "toolchain": {
            "nvcc": output(["nvcc", "--version"]),
            "cxx": output(["c++", "--version"]),
            "cmake": output(["cmake", "--version"]),
            "python": output(["python3", "--version"]),
            "node": output(["node", "--version"]),
            "python_packages": output(["python3", "-m", "pip", "freeze", "--all"]),
            "node_global_packages": output(["npm", "list", "--global", "--depth=0"]),
            "debian_packages": output(
                ["dpkg-query", "--show", "--showformat=${Package}=${Version}\\n"]
            ),
        },
    }


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def event(path: Path, kind: str, **details: Any) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {"timestamp": now(), "event": kind, **details}, sort_keys=True
            )
            + "\n"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    harness = Path(os.environ.get("FRNN_HARNESS", "/opt/frnn-harness"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--framework", required=True)
    parser.add_argument("--framework-version", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-version")
    parser.add_argument("--reasoning")
    parser.add_argument("--repetition", required=True, type=int)
    parser.add_argument("--budget-seconds", required=True, type=int)
    parser.add_argument("--image-ref")
    parser.add_argument(
        "--goal",
        type=Path,
        default=harness / "prompts" / "goal.txt",
    )
    parser.add_argument("--runs-root", type=Path, default=Path("/runs"))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("an agent command is required after --")
    if args.repetition < 1 or args.budget_seconds < 1:
        parser.error("repetition and budget must be positive")
    return args


def main() -> int:
    args = parse_args()
    workspace = Path(
        os.environ.get("FRNN_WORKSPACE", "/workspace/libFRNN")
    ).resolve()
    harness = Path(os.environ.get("FRNN_HARNESS", "/opt/frnn-harness"))
    run_dir = args.runs_root / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    goal_copy = run_dir / "goal.txt"
    goal_copy.write_bytes(args.goal.read_bytes())
    source_manifest = harness / "upstream" / "source-manifest.json"
    started = now()
    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "run_id": args.run_id,
        "treatment": {
            "framework": args.framework,
            "framework_version": args.framework_version,
            "model": args.model,
            "model_version": args.model_version,
            "reasoning": args.reasoning,
            "repetition": args.repetition,
            "command": args.command,
            "command_shell_escaped": shlex.join(args.command),
            "permissions": None,
            "network_policy": None,
            "context_policy": None,
        },
        "inputs": {
            "upstream_repository": "https://github.com/xju2/libFRNN",
            "upstream_commit": os.environ.get(
                "FRNN_UPSTREAM_COMMIT",
                "5ce9f21e2a2f12edfc5734fdd31973098a2f8d6d",
            ),
            "source_manifest_sha256": sha256(source_manifest),
            "goal_sha256": sha256(goal_copy),
            "datasets": datasets(workspace),
        },
        "environment": environment(args.image_ref),
        "budget": {
            "wall_seconds_limit": args.budget_seconds,
            "includes_build_and_evaluation": True,
            "tokens": None,
            "cost_usd": None,
        },
        "timestamps": {"started_at": started, "finished_at": None},
        "human_interventions": [],
        "outcome": {
            "status": "running",
            "termination_reason": None,
            "return_code": None,
            "wall_seconds": None,
            "output_commit": None,
            "correctness": None,
            "performance": None,
        },
        "artifacts": [],
        "notes": None,
    }
    manifest_path = run_dir / "manifest.json"
    events_path = run_dir / "events.jsonl"
    transcript_path = run_dir / "transcript.log"
    write_json(manifest_path, manifest)
    event(events_path, "run_started")

    started_monotonic = time.monotonic()
    status = "completed"
    reason = "agent_process_exited"
    return_code: int | None = None
    with transcript_path.open("wb") as transcript:
        process = subprocess.Popen(
            args.command,
            cwd=workspace,
            stdout=transcript,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            return_code = process.wait(timeout=args.budget_seconds)
            if return_code != 0:
                status = "failed"
                reason = "nonzero_exit"
        except subprocess.TimeoutExpired:
            status = "timed_out"
            reason = "wall_clock_budget_exhausted"
            os.killpg(process.pid, signal.SIGTERM)
            try:
                return_code = process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                return_code = process.wait()

    wall_seconds = time.monotonic() - started_monotonic
    # Intent-to-add makes untracked, non-ignored files visible to git diff.
    # Diffing from the root commit also includes changes the agent committed.
    subprocess.run(
        ["git", "-C", str(workspace), "add", "--intent-to-add", "--all"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    baseline_commit = output(
        ["git", "-C", str(workspace), "rev-list", "--max-parents=0", "HEAD"]
    )
    patch_path = run_dir / "result.patch"
    result_patch_capture = capture_command_output(
        patch_path,
        [
            "git",
            "-C",
            str(workspace),
            "diff",
            "--binary",
            baseline_commit or "HEAD",
        ],
    )
    worktree_patch_path = run_dir / "worktree.patch"
    worktree_patch_capture = capture_command_output(
        worktree_patch_path,
        ["git", "-C", str(workspace), "diff", "--binary", "HEAD"],
    )
    git_log_path = run_dir / "git-log.txt"
    git_log_capture = capture_command_output(
        git_log_path,
        [
            "git",
            "-C",
            str(workspace),
            "log",
            "--all",
            "HEAD",
            "--date=iso-strict",
            "--pretty=fuller",
            "--decorate=full",
        ],
    )
    bundle_path = run_dir / "repository.bundle"
    try:
        bundle_process = subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "bundle",
                "create",
                str(bundle_path),
                "--all",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        bundle_capture: dict[str, Any] = {
            "return_code": bundle_process.returncode,
            "stderr": bundle_process.stderr.strip() or None,
            "verified": False,
        }
        if bundle_process.returncode == 0 and bundle_path.is_file():
            verification = subprocess.run(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "bundle",
                    "verify",
                    str(bundle_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=120,
            )
            bundle_capture["verified"] = verification.returncode == 0
            bundle_capture["verification_stderr"] = (
                verification.stderr.strip() or None
            )
        else:
            bundle_path.unlink(missing_ok=True)
    except (OSError, subprocess.SubprocessError) as error:
        bundle_path.unlink(missing_ok=True)
        bundle_capture = {
            "return_code": None,
            "stderr": str(error),
            "verified": False,
        }
    manifest["timestamps"]["finished_at"] = now()
    manifest["outcome"].update(
        {
            "status": status,
            "termination_reason": reason,
            "return_code": return_code,
            "wall_seconds": wall_seconds,
            "output_commit": output(
                ["git", "-C", str(workspace), "rev-parse", "HEAD"]
            ),
            "baseline_commit": baseline_commit,
            "git_status": output(
                ["git", "-C", str(workspace), "status", "--short"]
            ),
            "git_capture": {
                "result_patch": result_patch_capture,
                "worktree_patch": worktree_patch_capture,
                "git_log": git_log_capture,
                "repository_bundle": bundle_capture,
            },
        }
    )
    artifact_paths = [
        goal_copy,
        transcript_path,
        events_path,
        patch_path,
        worktree_patch_path,
        git_log_path,
        bundle_path,
    ]
    manifest["artifacts"] = [
        {"path": path.name, "sha256": sha256(path)}
        for path in artifact_paths
        if path.is_file()
    ]
    event(
        events_path,
        "run_finished",
        status=status,
        return_code=return_code,
        wall_seconds=wall_seconds,
    )
    for artifact in manifest["artifacts"]:
        if artifact["path"] == "events.jsonl":
            artifact["sha256"] = sha256(events_path)
    write_json(manifest_path, manifest)
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

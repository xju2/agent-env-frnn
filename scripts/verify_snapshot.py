#!/usr/bin/env python3
"""Verify vendored files against their upstream Git blob identities."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=here.parent / "workspace")
    parser.add_argument("--manifest", type=Path, default=here.parent / "upstream" / "source-manifest.json")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    failures: list[str] = []
    for item in manifest["files"]:
        path = args.root / item["path"]
        if not path.is_file():
            failures.append(f"missing: {item['path']}")
            continue
        data = path.read_bytes()
        actual = git_blob_sha(data)
        if actual != item["blob_sha"]:
            failures.append(f"changed: {item['path']} ({actual} != {item['blob_sha']})")

    if failures:
        print("Snapshot verification failed:")
        print("\n".join(f"  {line}" for line in failures))
        return 1
    print(f"Verified {len(manifest['files'])} files from {manifest['upstream_commit']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Run records

A scientific run record should answer three questions independently of a vendor UI: exactly what the agent saw, exactly what was allowed and consumed, and exactly what code and measurements resulted.

Use `run-frnn-experiment` to create the core record. Extend `manifest.json` with raw benchmark samples and correctness results after evaluation. Do not overwrite a completed run; create a new `run_id` for reruns. If a human sends any message, changes a file, restarts a command, or selects a hypothesis after the timer starts, append a timestamped object to `human_interventions` and do not label the run fully autonomous.

Commit completed manifests, patches, event logs, and compact benchmark results. Large transcripts or profiler captures can live in external object storage, but record their URI, byte size, and SHA-256 digest in the manifest.

The JSON Schema intentionally permits additional fields so framework-specific telemetry can be retained. Never omit a core field because it is unavailable; use `null` and explain the limitation in `notes`.

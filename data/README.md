# External benchmark data

The historical checkpoint references two real-life inputs that are not tracked in the upstream Git repository:

- `embedding_data.csv`
- `edge_list.csv`

Place them in a host directory and mount that directory read-only at `/workspace/libFRNN/data` for every experiment. Use the exact same bytes for every agent and repetition. `run-frnn-experiment` records the SHA-256 digest and size of each file it finds there.

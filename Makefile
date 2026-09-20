IMAGE ?= agent-env-frnn:cuda13.0-pytorch2.13

.PHONY: image shell smoke verify

image:
	docker build --pull --tag "$(IMAGE)" .

shell:
	docker run --rm -it --gpus '"device=0"' \
		-e EXPECTED_GPU_REGEX='RTX 2070' \
		-e EXPECTED_COMPUTE_CAPABILITY=7.5 \
		-v "$(CURDIR)/runs:/runs" \
		"$(IMAGE)"

smoke:
	docker run --rm --gpus '"device=0"' \
		-e EXPECTED_GPU_REGEX='RTX 2070' \
		-e EXPECTED_COMPUTE_CAPABILITY=7.5 \
		"$(IMAGE)" smoke-test-frnn

verify:
	python3 scripts/verify_snapshot.py

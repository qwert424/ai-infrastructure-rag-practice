DS ?= all

# 集成测试使用的沙箱镜像；可用 make test-integrations DEPLOY_SANDBOX_IMAGE=xxx 覆盖。
DEPLOY_SANDBOX_IMAGE ?= opensandbox-python-node:1.0

# Windows 的 cmd 与 POSIX shell 设置环境变量的语法不同，这里统一处理。
ifeq ($(OS),Windows_NT)
INTEGRATION_ENV = set "MINIO_INTEGRATION=1" && set "DEPLOY_INTEGRATION=1" && set "DEPLOY_SANDBOX_IMAGE=$(DEPLOY_SANDBOX_IMAGE)" &&
else
INTEGRATION_ENV = MINIO_INTEGRATION=1 DEPLOY_INTEGRATION=1 DEPLOY_SANDBOX_IMAGE=$(DEPLOY_SANDBOX_IMAGE)
endif

.PHONY: docker-recreate build dev debug test-benchmark test-units test-integrations

docker-recreate:
	docker compose up -d --force-recreate

build:
	uv run langgraph build -t langgraph-python-agent:$(TAG)

dev:
	uv run langgraph dev --host 0.0.0.0 --port 80 --allow-blocking

debug:
	uv run langgraph dev --host 0.0.0.0 --port 80 --debug-port 5678 --allow-blocking

test-benchmark:
	BENCHMARK_DATASET="$(DS)" uv run pytest -q -s --tb=no tests/benchmarks/test_benchmark.py

test-units:
	uv run pytest -q tests/units

test-integrations:
	$(INTEGRATION_ENV) uv run pytest -q tests/intergrations

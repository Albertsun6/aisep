# 统一的 test / lint / demo / eval 入口（本地与 CI 共用同一脚本，避免 pip vs uv、本地 vs CI 漂移）
PY ?= python3
export PYTHONPATH := src

.PHONY: help test lint arch fmt demo eval clean install-dev

help:
	@echo "make test       跑全部测试（标准库 unittest，无需安装）"
	@echo "make demo       端到端规格驱动 + 多 agent 编排（mock LLM，离线）"
	@echo "make eval       跑 eval 集，输出四个生产指标"
	@echo "make lint       ruff 静态检查（需 requirements-dev.txt）"
	@echo "make arch       import-linter 架构契约（对照 .importlinter 锁分层边界）"
	@echo "make fmt        ruff 自动格式化"
	@echo "make install-dev 安装可选开发依赖"

test:
	$(PY) -m unittest discover -s tests -p "test_*.py" -v

demo:
	$(PY) -m aiforge.cli demo

eval:
	$(PY) -m aiforge.cli eval --dataset eval/dataset.jsonl

lint:
	ruff check src tests

arch:
	lint-imports

fmt:
	ruff format src tests
	ruff check --fix src tests

install-dev:
	$(PY) -m pip install -r requirements-dev.txt

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .ruff_cache .pytest_cache

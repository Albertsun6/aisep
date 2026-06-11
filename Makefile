# 统一的 test / lint / demo / eval 入口（本地与 CI 共用同一脚本，避免 pip vs uv、本地 vs CI 漂移）
PY ?= python3
export PYTHONPATH := src

.PHONY: help test lint arch fmt demo eval clean install-dev hooks gate-commit gate-feature

help:
	@echo "make test       跑全部测试（标准库 unittest，无需安装）"
	@echo "make demo       端到端规格驱动 + 多 agent 编排（mock LLM，离线）"
	@echo "make eval       跑 eval 集，输出四个生产指标"
	@echo "make lint       ruff 静态检查（需 requirements-dev.txt）"
	@echo "make arch       import-linter 架构契约（对照 .importlinter 锁分层边界）"
	@echo "make fmt        ruff 自动格式化"
	@echo "make install-dev 安装可选开发依赖"
	@echo "make hooks      安装 repo 内 git hooks（core.hooksPath=.githooks，反馈层）"
	@echo "make gate-commit  本地聚合门禁（pre-commit 同款；0/1/2/3 见 specs/contracts/03）"
	@echo "make gate-feature 门禁链全量（CI 'gates' check 同款）"

test:
	$(PY) -m unittest discover -s tests -p "test_*.py" -v

demo:
	$(PY) -m aiforge.cli demo

eval:
	$(PY) -m aiforge.cli eval --dataset eval/dataset.jsonl

lint:
	$(PY) -m ruff check src tests

arch:
	lint-imports

fmt:
	$(PY) -m ruff format src tests
	$(PY) -m ruff check --fix src tests

install-dev:
	$(PY) -m pip install -r requirements-dev.txt

hooks:
	git config core.hooksPath .githooks
	@echo "已启用 .githooks/(反馈层;权威在 CI——specs/contracts/01)"

gate-commit:
	$(PY) -m aiforge gate-commit

# CI 'gates' required check 的聚合链(契约 01);本地也可全量自检
gate-feature: lint arch test
	$(PY) -m aiforge gate-commit --ci

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .ruff_cache .pytest_cache

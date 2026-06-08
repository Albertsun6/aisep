# 安全策略 / Security Policy

## 报告漏洞 / Reporting a Vulnerability

请**不要**在公开 issue 中披露安全问题。请通过私密渠道联系维护者（GitHub Security
Advisory 的 "Report a vulnerability"，或维护者私信）。我们会在收到后尽快确认并修复。

Please do **not** open a public issue for security problems. Report privately via
GitHub Security Advisories ("Report a vulnerability") or a direct message to the
maintainer. We will acknowledge and address reports as soon as possible.

## 范围 / Scope

本项目是"用 AI 工程化方式开发企业软件"的参考系统，核心引擎纯标准库、零运行时第三方依赖。
关注点包括但不限于：

- 质量门禁绕过（`quality/gates.py` fails-closed 不变量）
- 权限 / 沙箱越界（`governance/permissions.py`、`runtime/` 隔离）
- 不可信 LLM 生成代码的执行隔离（`runtime/isolation.py`）
- 凭据泄露（禁止硬编码密钥、禁止提交 `.env`）

## 不在范围 / Out of Scope

- 可选接入依赖（`requirements-dev.txt` 中的 langgraph / openhands 等）的上游漏洞——请上报对应上游项目。

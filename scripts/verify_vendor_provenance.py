#!/usr/bin/env python3
"""spec: specs/feat-bpmn 验收 17(2026-06-12 异构评审修订)— vendor 来源重验(纯标准库)。

关闭"恶意 vendor 文件 + 配套 SHA256SUMS 自洽"通道:SHA256SUMS 只证自洽不证来源,
本脚本把每个 `docs/vendor/<name>@<version>/` 包与 **npm registry 官方 tarball** 逐字节
对账——registry 元数据给出 tarball 的 sha512 integrity,先验 tarball,再要求 vendor 内
每个文件(除我们自己的 SHA256SUMS 清单)的 sha256 都出现在官方 tarball 的文件集合里。

用法:
  python3 scripts/verify_vendor_provenance.py [--base <sha>] [--repo <path>]
  --base 给定时,基于 `git diff --name-only <sha>...HEAD`:vendor 无变更 → skip(exit 0)。
CI 中 vendor 有变更而 registry 不可达/不匹配 → exit 1(fail-closed)。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

VENDOR_REL = "docs/vendor"
REGISTRY = "https://registry.npmjs.org"


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 - 固定 https registry
        return r.read()


def _changed_vendor_paths(repo: Path, base: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=str(repo), check=True, capture_output=True, text=True,
    ).stdout
    return [ln for ln in out.splitlines() if ln.startswith(VENDOR_REL + "/")]


def verify_package(pkg_dir: Path) -> list[str]:
    """返回问题清单;空 = 通过。"""
    problems: list[str] = []
    dirname = pkg_dir.name
    if "@" not in dirname:
        return [f"{dirname}: 目录名不含 @version,无法定位 registry 版本"]
    name, version = dirname.rsplit("@", 1)
    meta = json.loads(_fetch(f"{REGISTRY}/{name}/{version}").decode("utf-8"))
    dist = meta.get("dist") or {}
    tarball_url, integrity = dist.get("tarball"), dist.get("integrity", "")
    if not tarball_url or not integrity.startswith("sha512-"):
        return [f"{dirname}: registry 元数据缺 tarball/integrity"]
    blob = _fetch(tarball_url)
    actual = "sha512-" + base64.b64encode(hashlib.sha512(blob).digest()).decode()
    if actual != integrity:
        return [f"{dirname}: tarball sha512 与 registry integrity 不符(供应链告警)"]
    official: set = set()
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        for m in tf:
            if m.isfile():
                f = tf.extractfile(m)
                if f is not None:
                    official.add(hashlib.sha256(f.read()).hexdigest())
    for p in sorted(pkg_dir.rglob("*")):
        if not p.is_file() or p.name == "SHA256SUMS":
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() not in official:
            problems.append(f"{dirname}/{p.relative_to(pkg_dir)}: 内容不在官方 tarball 中(被改动或来源不明)")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None, help="对比基线 sha;vendor 无变更则跳过")
    ap.add_argument("--repo", default=".", help="repo 根")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    vendor = repo / VENDOR_REL
    if args.base:
        changed = _changed_vendor_paths(repo, args.base)
        if not changed:
            print("vendor-provenance: 本次无 vendor 变更,跳过")
            return 0
        print(f"vendor-provenance: 检测到 {len(changed)} 个 vendor 路径变更,开始对 registry 重验")
    if not vendor.is_dir():
        print("vendor-provenance: 无 docs/vendor 目录,跳过")
        return 0
    all_problems: list[str] = []
    for pkg_dir in sorted(d for d in vendor.iterdir() if d.is_dir()):
        try:
            problems = verify_package(pkg_dir)
        except Exception as e:  # 网络/解析失败 → fail-closed
            problems = [f"{pkg_dir.name}: 重验失败({e})"]
        status = "OK" if not problems else "FAIL"
        print(f"  [{status}] {pkg_dir.name}")
        all_problems.extend(problems)
    for p in all_problems:
        print(f"  !! {p}", file=sys.stderr)
    return 1 if all_problems else 0


if __name__ == "__main__":
    sys.exit(main())

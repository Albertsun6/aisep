"""eval 数据集：用**真实工程任务**而非纯基准（调研建议自建 lightweight eval 集）。

JSONL，每行一个任务。``evidence`` 模拟 CI/扫描结果，便于离线确定性地驱动门禁与指标。
真实接入时，evidence 由真实 runtime 跑测试 / SAST / 覆盖率工具产出。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class EvalTask:
    id: str
    request: str
    task_type: str = "feature"
    evidence: Dict[str, object] = field(default_factory=dict)
    expected_human_review: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "EvalTask":
        return cls(
            id=d["id"],
            request=d["request"],
            task_type=d.get("task_type", "feature"),
            evidence=d.get("evidence", {}),
            expected_human_review=bool(d.get("expected_human_review", False)),
        )


def load_dataset(path: str) -> List[EvalTask]:
    tasks: List[EvalTask] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tasks.append(EvalTask.from_dict(json.loads(line)))
    return tasks

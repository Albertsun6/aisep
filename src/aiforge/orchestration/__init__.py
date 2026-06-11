"""编排层：supervisor + 角色 agent，通过共享状态通信。"""

from aiforge.orchestration.state import (
    Artifact,
    ArtifactKind,
    PipelineState,
    Status,
    Task,
)


def __getattr__(name):
    # Supervisor / build_default_pipeline **延迟导入**（PEP 562）：避免 import aiforge.orchestration[.state] 期就拉
    # graph→agents→runtime.base 成环。真正用到时才加载（此时 runtime.base 已完成）。破循环 import 的根因修法，
    # 使 base/review 可在运行期正常 import FileChange（get_type_hints 不再 NameError）。
    if name in ("Supervisor", "build_default_pipeline"):
        from aiforge.orchestration import graph
        return getattr(graph, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Artifact",
    "ArtifactKind",
    "PipelineState",
    "Status",
    "Task",
    "Supervisor",
    "build_default_pipeline",
]

# toy-csv-export — demo 流水线结果导出 CSV

status: active
目标:一句话——`aiforge demo` 跑完后能把产物清单导出为 CSV,供人用表格工具查看。

## 背景与范围

- 背景:demo 流水线结束只在终端打印产物;想要一个可存档、可用 Excel/Numbers 打开的产物清单。
- 范围内:新增 `--csv <path>` 选项;导出列 = artifact kind / produced_by / refs / 创建时间。
- **不做**:不导出文件内容本身;不做 Excel(xlsx)格式;不改动 demo 流水线逻辑。

## 验收标准(Gherkin)

- Given demo 流水线成功跑完
  When 用户执行 `python -m aiforge demo --csv out.csv`
  Then 在 out.csv 生成 UTF-8 CSV,首行为表头,每个 artifact 一行。
- Given 目标路径的父目录不存在
  When 用户执行 `--csv missing/dir/out.csv`
  Then 命令以非 0 退出并打印可读错误,不静默吞错。
- Given 用户未传 `--csv`
  When demo 正常结束
  Then 行为与现状完全一致(不产生任何文件)。

## 非功能清单(P6)

- 错误处理:路径不可写/父目录缺失 → 非 0 + 诊断(见验收 2);
- 安全:导出内容不含 secret(产物内容本就不导出);路径不做展开/遍历;
- 可观测:导出成功打印行数与路径;
- 限流:N/A——本地一次性写文件,无外部调用;
- 审计:N/A——只读导出,不改变状态(审计由现有 trail 覆盖)。

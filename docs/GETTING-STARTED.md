# 手把手上手教程 — 跟着敲就能跑通

> 这份是**操作教程**(照着一步步做),不是参考手册。每一步给:① 要敲的命令 ② 你会看到什么(真实输出) ③ 卡住了怎么办。
> 参考型的完整命令表见 [USER-GUIDE.md](USER-GUIDE.md);本文只带你**从零跑通一个特性**。
> 全程约 15 分钟。下面所有"你会看到"都是真机跑出来的,不是示意。

---

## 准备:5 个一次性动作

### 第 0 步 · 拿到代码

```bash
git clone https://github.com/Albertsun6/aisep.git
cd aisep
```

### 第 1 步 · 确认能跑(零安装)

```bash
make test
```

**你会看到**(屏幕会滚过很多 `gate-spec: rejected` / `approved` 之类的日志——**别慌**,那是测试在内部断言门禁的拒绝行为,不是出错。只看**最后两行**):

```
Ran 78 tests in 6.4s
OK
```

> ✅ 看到 `OK` = 环境没问题。本项目纯标准库,不需要 pip install。

### 第 2 步 · 装 lint 依赖(门禁要用)

```bash
make install-dev
```

装的是 `ruff`(代码格式检查)和 `import-linter`(架构契约)。**不装会怎样?** 后面 `gate-commit` 的 lint 步骤会直接退出码 3(基础设施错误),不是放行——所以先装上。

### 第 3 步 · 启用本地门禁

```bash
make hooks
```

**你会看到**:

```
git config core.hooksPath .githooks
已启用 .githooks/(反馈层;权威在 CI——specs/contracts/01)
```

> 从此每次 `git commit` 会自动跑门禁。这是**反馈层**,真正拦不住的(GitHub CI)在最后一步讲。

### 第 4 步 · 记住一条铁律

> **改 `src/` 或 `tests/` 的代码,提交时必须说它属于哪个"特性"(feature),而且那个特性得先有过 spec。** 否则提交被拒。这就是"无规格不写代码"。下面整个流程就是带你正确地走完一个特性。

---

## 主线:从零做完一个特性(7 步)

我们做一个玩具特性:给 `aiforge demo` 加一个 `--greeting` 选项,结束时多打印一行问候。feature-id 取 `hello-greeting`(小写,用连字符)。

### 第 5 步 · 写需求 spec

每个特性一个目录 `specs/<feature-id>/`。先建目录、写 `spec.md`:

```bash
mkdir -p specs/hello-greeting
```

把下面内容存成 `specs/hello-greeting/spec.md`:

```markdown
# hello-greeting — demo 增加一句问候

status: active
目标:`aiforge demo` 结束时多打印一行可配置的问候语。

## 验收标准(Gherkin)
- Given demo 流水线跑完
  When 用户执行 `python -m aiforge demo --greeting 你好`
  Then 终端额外打印一行 "问候: 你好"。
- Given 用户未传 --greeting
  When demo 正常结束
  Then 不打印任何问候行(行为与现状一致)。

## 非功能清单(P6)
- 错误处理:greeting 为空字符串时不打印(等同未传);
- 安全:greeting 原样打印,不做 shell/eval;
- 可观测/限流/审计:N/A(本地一次性打印)。
```

> **spec 必须有"验收结构"**:Gherkin(Given/When/Then)、EARS(... shall ... when/if)、或 User Story + 验收标记,三选一,且整体 ≥40 字符。门禁就查这个。

### 第 6 步 · 过第一道门:gate-spec

```bash
PYTHONPATH=src python3 -m aiforge gate-spec specs/hello-greeting/spec.md
```

**你会看到**:

```
gate-spec: approved (exit 0)
```

> ✅ `exit 0` = 通过。同时它在 `specs/hello-greeting/gates/gate-spec.json` 写了一张"回执"(receipt),记下这份 spec 的指纹。**这一刻起 spec 就冻结了**——以后改它必须重跑 gate-spec,否则后面的门禁会发现指纹对不上。
>
> ⚠️ **`PYTHONPATH=src` 不能省**!本项目不是 pip 安装的,少了它会报 `No module named aiforge`。嫌长可以先 `export PYTHONPATH=src`,本终端后续就不用每次带。

**没过怎么办?** 如果看到 `rejected (exit 1)` 并提示"缺验收结构",就是 spec 里没有 Given/When/Then 这类结构,或太短。补上再跑。

### 第 7 步 · 写架构 plan 和拆分 tasks

这两个是文档,声明"我依赖上游谁"。存成 `specs/hello-greeting/plan.md`:

```markdown
# hello-greeting · plan

> refs: spec.md

- 落点:`src/aiforge/cli.py` 的 `_cmd_demo`,加 `--greeting` 选项,demo 末尾按需打印。
- 不改编排/门禁;空串等同未传。
```

和 `specs/hello-greeting/tasks.md`:

```markdown
# hello-greeting · tasks

> refs: plan.md

| # | 任务 | 验收 |
|---|---|---|
| T1 | `_cmd_demo` 加 --greeting,末尾打印 "问候: X" | spec 验收 1/2 |
| T2 | tests/test_demo_greeting.py 覆盖:传/不传/空串 | make test 绿 |
```

> 注意那行 `> refs: spec.md` / `> refs: plan.md`——这是"追溯链"声明,下一道门会查它能不能解析到真实的上游文件。

### 第 8 步 · 过追溯门:gate-trace

```bash
PYTHONPATH=src python3 -m aiforge gate-trace specs/hello-greeting
```

**你会看到**:

```
gate-trace: approved (exit 0)
```

> 它检查 `plan.md` 声明了 `> refs: spec.md` 且 spec.md 真存在、`tasks.md` 声明了 plan.md 且 plan.md 真存在。链没断就过。
>
> **常见错**:`rejected (exit 1)` 提示"未声明上游 refs"——就是你忘了写 `> refs: xxx` 那行。

### 第 9 步 · 写代码 + 写测试

现在才动 `src/`。打开 `src/aiforge/cli.py`,在 `_cmd_demo` 函数里 `print(f"审计事件数...")` 那行**之前**加:

```python
    if getattr(args, "greeting", None):
        print(f"问候: {args.greeting}")
```

并在 `--csv` 选项那行**之前**加一个新选项:

```python
    p_demo.add_argument("--greeting", default=None, help="demo 末尾打印一行问候")
```

再写测试 `tests/test_demo_greeting.py`:

```python
"""spec: specs/hello-greeting"""
import contextlib
import io
import unittest

from aiforge.cli import main as cli_main


class TestGreeting(unittest.TestCase):
    def test_prints_when_given(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli_main(["demo", "--approve", "--greeting", "你好"]), 0)
        self.assertIn("问候: 你好", out.getvalue())

    def test_silent_when_absent(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli_main(["demo", "--approve"]), 0)
        self.assertNotIn("问候:", out.getvalue())


if __name__ == "__main__":
    unittest.main()
```

跑测试确认特性真的работает:

```bash
make test
```

**你会看到** `Ran 80 tests ... OK`(比之前多 2 个,就是你刚加的)。

### 第 10 步 · 提交前自查:gate-judge

把改动加入暂存区,跑静态风险扫描:

```bash
git add -A
PYTHONPATH=src python3 -m aiforge gate-judge --staged
```

**你会看到**:

```
gate-judge: approved (exit 0)
```

> 它扫你的 diff 有没有 `eval()` / `os.system` / 拼接 SQL / 硬编码密钥这类危险模式。**注意:它永远不调用 AI 模型**,纯正则静态扫描。干净就 `exit 0`。

### 第 11 步 · 正式提交(自动过聚合门禁)

```bash
AIFORGE_FEATURE=hello-greeting git commit -m "feat(hello-greeting): demo --greeting prints a line"
```

注意前面的 `AIFORGE_FEATURE=hello-greeting`——这就是"声明这次改动属于哪个特性"。提交时 `.githooks/pre-commit` 自动跑聚合门禁,**你会看到**它打印一份"三文件 review 清单"(P7 协议名;实际会把本次**所有**改动文件按 diff 大小列出,前几个标 `[必读]`、其余 `[抽审]`——所以会有 spec/plan/tasks/receipt/代码/测试好几行,数量取决于你改了多少),最后一行是:

```
...(若干 [必读]/[抽审] 文件行)...
gate-commit: approved (exit 0)
```

> ✅ 关键看**最后一行** `gate-commit: approved (exit 0)` = 提交成功。聚合门禁一次过了四关:feature 声明在不在、receipt 链全不全、lint 过没过、静态风险有没有。中间那些文件行是给你的人工 review 提示,不是错误。

**验证特性真生效**:

```bash
PYTHONPATH=src python3 -m aiforge demo --approve --greeting 你好
```

输出里会有一行 `问候: 你好`(在 `审计事件数: N` 那行之前)。🎉 你完整走完了一个特性。

---

## 必看:门禁拦住你时,长什么样

上面是顺利路径。真实开发里门禁会拦你——这是它的本职。下面三种是你**一定会遇到**的,提前认识:

### 拦截 A · lint 没过(最常见)

提交时如果代码格式不规范(比如多语句写一行),`gate-commit` 直接拒。**自己造一个体验**——往测试文件追加一行同行语句再提交:

```bash
printf '\nif True: x = 1\n' >> tests/test_demo_greeting.py
git add -A
AIFORGE_FEATURE=hello-greeting git commit -m "试触发 lint"
```

**你会看到**(真实 ruff 输出,行号/列号随你的文件而变):

```
lint 未通过:
  E701 Multiple statements on one line (colon)
   --> tests/test_demo_greeting.py:27:8
Found 1 error.
gate-commit: rejected (exit 1)
```

**怎么办**:跑自动修,再提交:

```bash
make fmt        # ruff 自动修格式
make test       # 确认没改坏
# 然后重跑你的 git commit
```

> 少数 ruff 不能自动修的(如多语句同行),按提示手动改那一行。

### 拦截 B · 改了代码但没声明 feature

```bash
echo "x = 1" >> src/aiforge/config.py
git add -A
git commit -m "随手改"
```

**你会看到**:

```
src/tests 改动必须声明 feature:--feature <id> 或 AIFORGE_FEATURE=<id>(契约 02)
gate-commit: rejected (exit 1)
```

**怎么办**:这个改动属于哪个特性?给它建 spec(回第 5 步),或用 `AIFORGE_FEATURE=<已有特性> git commit`。**没有"我就想随手改一行"的后门**——这是设计,不是 bug。

### 拦截 C · 代码里有危险模式

```bash
printf 'def run(c):\n    return eval(c)\n' > danger.py
git add danger.py
PYTHONPATH=src python3 -m aiforge gate-judge --staged
```

**你会看到**:

```
[blocker] eval() 可能 RCE(静态扫描只升级人审,不裁决)
人审清单:确认上述命中是误报或已有补偿控制,放行走契约 07 通道
gate-judge: needs_human (exit 2)
```

> **`exit 2` 不是"拒绝",是"转人审"**。意思:机器不替你拍板,要人看一眼。如果确认是误报(比如你确实需要 eval 且有防护),本地放行用 `gate-commit --ack-human`(需要真终端;**只是审计记录**)。真正的放行是 GitHub 上由人类账号 approve PR——CI 不认本地 ack。

### 拦截 D · 偷改已冻结的 spec

如果你过了 gate-spec 之后又改 spec.md 但不重跑,CI 用的只读校验命令 `gate-spec --check` 会抓到:

```bash
echo "## 偷偷加的需求" >> specs/hello-greeting/spec.md
PYTHONPATH=src python3 -m aiforge gate-spec --check specs/hello-greeting/spec.md
```

**你会看到**:

```
冻结校验:spec.md 内容与 receipt 记录的 hash 不符——改了冻结 spec 却未重跑 gate-spec(或 receipt 被伪造)。授权变更须走 specs/contracts/02 流程后重跑 gate-spec。
gate-spec --check: rejected (exit 1)
```

> 注意 `--check` 是**只读**的(不重新生成 receipt),专门给 CI 抓"改了冻结 spec 不重跑"。你本地平时用的是不带 `--check` 的 `gate-spec`(它会写新 receipt)。

**怎么办**:改 spec 是允许的,但要走正道——改完**重跑** `gate-spec`(不带 `--check`)生成新 receipt,再提交。

---

## 退出码速记(贴在显示器边上)

| 看到 | 意思 | 你该做 |
|---|---|---|
| `exit 0` | 通过 | 继续 |
| `exit 1` | 内容问题(缺 spec / 链断 / lint 没过 / 没声明 feature) | 按提示修内容,重跑 |
| `exit 2` | 转人审(静态扫描命中) | 人看一眼;误报就 `--ack-human`(仅本地)或走 PR approval |
| `exit 3` | 环境问题(没装 ruff / 没带 PYTHONPATH / receipt 坏) | 修环境,不是改代码 |

---

## 最后一关:推到 GitHub(真正的强制层)

本地门禁都是"反馈",可以 `git commit --no-verify` 绕过(明文承认)。**真正绕不过的是 GitHub CI**。

```bash
# 如果你有推送权限:
git push origin <你的分支>
# 然后在 GitHub 开 PR
```

PR 上会自动跑名为 `gates` 的检查,它会**重新**跑一遍 gate-spec(冻结校验)/gate-trace/gate-judge/lint/测试,任一不过就**红、禁止合并**。这一层对 AI 和人同等生效,本地怎么绕都没用。

> ⚠️ 本仓库当前 `enforce_admins=false`(单人开发的裁决)——意味着 repo 管理员(你)能 bypass 这层。多人协作时记得去 GitHub 把它重开,否则强制层对你自己不生效。

---

## 一页流程图(记不住时看这个)

```
建 specs/<id>/spec.md  ──►  gate-spec        (exit 0?)
       │
       ▼
写 plan.md + tasks.md  ──►  gate-trace       (exit 0?)
       │
       ▼
写 src/ 代码 + tests/  ──►  make test 绿
       │
       ▼
git add -A             ──►  gate-judge       (0 过 / 2 转人审)
       │
       ▼
AIFORGE_FEATURE=<id>
git commit             ──►  gate-commit      (feature+receipt+lint+judge)
       │
       ▼
git push + 开 PR       ──►  GitHub CI 'gates' (唯一真强制,绕不过)
```

卡在哪一步,就回看上面对应章节的"没过怎么办"。完整命令参考见 [USER-GUIDE.md](USER-GUIDE.md)。

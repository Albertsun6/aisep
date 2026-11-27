## ADR-018 · 2026-11-21

- **状态**：已采纳（Albert 2026-11-21 拍板，经协调会话转达）
- **决策**：删除 `vendor/` 中未被使用、且未声明许可的文件，不算规范 §11 所说的"升级上游"，不需要批准记录，走普通 PR。判断是否声明了许可，要同时看文件自身（`cc:license`、`dcterms:license` 等）和上游 catalog 按数据集的声明（`ttl/catalog.ttl` 中 `dcat:Dataset` 的 `dcterms:license`）。本次按此只删除 `vendor/meta.linked.archi/llms.txt`，来源与理由见该目录的 `REMOVED.txt`。
- **理由**：仓库已公开并采用 Apache-2.0，没有许可声明的第三方文件会带来许可风险。`llms.txt` 不来自 `ttl/` 那次抓取，自身没有许可声明，catalog 里也没有它的条目，AISEP 也没有任何地方引用它。PR #31 的 NOTICE 只看了文件自身的 `cc:license`，把另外 14 个文件也算作无许可：其中 `catalog.ttl` 用 `dcterms:license` 声明了 CC BY 4.0；其余 13 个由 `catalog.ttl` 按数据集逐一声明为 CC BY 4.0。这 14 个都保留。
- **后果**：被删文件记入 `REMOVED.txt`；`FETCHED_AT`、`fetch.log`、`urls.txt`、`SHA256SUMS` 不变。`NOTICE` 把那 13 个文件改列为"许可由 catalog.ttl 按数据集声明为 CC BY 4.0"。以后核对 vendor 许可，两处声明都要看。

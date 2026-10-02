# Phase 2 — 从「一次判断」到「一只股票的档案」

> 状态：草案，待 review（2026-10-02）。
> 目标：走通 `docs/WORKFLOW.md` 的场景——10-01 盘后问「AMD 明天能买吗」，系统列出待回答的问题；人只编辑档案文件、重复运行同一条管道，就能得到「计划可执行 / 暂停 / 过期」的结论。
> 约束：遵守 `docs/DESIGN.md` 与 `docs/WORKFLOW.md` §0 原则。不新增 CLI 命令；不增加概念，除非万不得已（每步写明概念账）；工具层、取数、结构判定不动。

每一步结束时 `uv run pytest -q` 与 `uv run ruff check .` 都通过。

**预算**：包现为 2175 行（上限 ≈ 2200）。Phase 2 删除的代码（manual / todo / memo、规则覆盖章节、`RunOutput.idle`）要抵消新增；目标净增 ≈ 0。

## ① 档案文件

- `data/structures/<TICKER>.yaml` → `data/tickers/<TICKER>.yaml`，新增三段：`idea`、`facts`、`plans`（格式见 WORKFLOW §3）。
- `adapters/structures.py` → 读整份档案；`Snapshot` 新增 `idea`、`facts`；`plans` 转为 `Candidate` 注入（见 ④）。
- 迁移 `AMD.yaml`；结构相关的测试改路径。
- 概念账：文件改名扩充，不新增概念。

## ② 人工回答工具

- `fact: {key, is, ttl}`：`facts[key].value == is` → True；缺失或过期 → None（missing=False，即提问而非缺数据）。
- `checklist: {keys, min, ttl}`：任一 key 缺失或过期 → None，evidence 列出缺的 key；否则满足项数 < min → True（否决）。
- `ttl`：交易日数，或 `earnings`（到下次财报；无财报日按 63 个交易日）。按 `session_date` 与回答的 `at` 计算。
- 纯函数测试：过期边界、earnings 回退、缺 key 列表。
- 概念账：+ 人工回答（facts）。

## ③ 规则迁移：manual → veto + ask + fact

- 执行器：删除 `kind: manual` / `kind: todo` 与 `trust: memo`；任何块可写 `ask:`，块未知时 `ask` 作为提问文本放在 evidence 首位。`parse` 校验同步更新。
- playbook 改写：
  - 新增 **0. 想法** 一节，`I01 写下想法理由`：`fact` 读 `idea`，缺失 → 提问。
  - V06、V08、V10b：`fact`，ttl 1 / 1 / 5。
  - V07：原四个条件 + `fact: {key: v07.no_bad_news, is: false, ttl: 1}`；Kleene 保证只在其余条件成立时才提问。
  - V09：`checklist`（WORKFLOW §5 的 9 项，`min: 7`，`ttl: earnings`）。
  - S08：见「待确认」。
- 测试（真实 playbook）：V09 清单 6/9 → VETO、7/9 → PASS、缺 1 项 → 提问；V07 上涨中不提问；I01 缺理由 → 提问。
- 概念账：− manual、− todo、− memo；DESIGN §3–§4 同步。

## ④ 计划生命周期

- `Candidate` 新增 `expires: date | None`、`status: str = "active"`（setup 产出的候选不填）。
- 档案中的 `plans` → Candidate 注入运行；`status: cancelled` 不进入运行；`expires` 省略 = `at` + 20 个交易日。
- 「暂停」「过期」由报告计算，不存储：
  - 过期：`session_date > expires`。
  - 暂停：该计划存在 decide 的 VETO 或未知（含上下文规则）。
- 测试：过期边界；V12 否决 → 暂停；否决解除 → 恢复可执行。
- 概念账：计划 = Candidate + 两个字段，不新增概念。

## ⑤ 报告：档案视图

- 章节按 WORKFLOW §7：结论 → 待回答 → 计划 → 系统建议买点 → 提醒。
- 结论一行，按优先级：先写想法理由 / 不买（否决原因）/ 待回答 N 项 / 审查通过，尚无计划 / 计划 p1 可执行 / 计划 p1 暂停（原因）/ 计划 p1 已过期。
- 待回答：每项 = 规则 ID + 提问 + 需填写的 key。
- 删除「规则覆盖」章节与 `RunOutput.idle`（RunOutput JSON 已含全部信息）。
- 保留报告头的结构信息行（Phase 1 M2）。
- 测试：每种结论各一例。

## ⑥ 日志

- `data/journal/<TICKER>.jsonl`：每次运行追加一行，只追加不修改；不买也记。
- 做法取决于「待确认 3」：倾向 `run --compact` 输出单行 JSON，由 shell `tee -a` 追加，不新增命令。
- 概念账：+ 日志（只是文件，无代码概念）。

## ⑦ 场景验收

- `tests/unit/test_workflow.py`：用 fake 行情 + 真实 playbook 走完整循环：
  1. 只有 ticker → 「先写想法理由」。
  2. 写入 idea → 「待回答 N 项」（V06 / V07 / V08 / V09 / V10b）。
  3. 写入回答 → 「审查通过，尚无计划」，附系统建议买点。
  4. 写入 plan → 「计划 p1 可执行」。
  5. 次日行情触发 V12 → 「计划 p1 暂停（V12 …）」；再次日 → 恢复。
  6. 超过 expires → 「计划 p1 已过期」。
- 文档：WORKFLOW 状态改为「已确认」；DESIGN 写入概念账；CLAUDE.md 入口表加入 WORKFLOW。
- 实跑：`tradesys fetch AMD | tradesys run … | tradesys report …` 在真实档案上输出档案视图。

## 待确认（review 时决定）

1. **改名**：`data/structures/` → `data/tickers/`？
2. **V09 清单**：WORKFLOW §5 的 9 项与 `min: 7`？
3. **日志内容**：整份 RunOutput 含行情（约 50KB/行，一年约 12MB/只），还是只记结论、回答、计划与规则状态（不含 bars）？
4. **结构过期**：Phase 1 M2 定为「只显示确认距今天数，不判过期」；WORKFLOW §4 提议 20 个交易日后过期并提问。取哪一个？
5. **S08**（板块龙头，纯人工的买点）：manual 删除后改为 advice 提醒，还是用 `fact` 回答后由人自行写入计划？
6. **想法规则 ID**：`I01`，放在 playbook 新增的「0. 想法」一节？
7. **回答的值类型**：V1 只支持布尔（`is: true / false`）？数字阈值（如跟踪月数）留到估值清单再说。

## 不在 Phase 2

- 估值清单（WORKFLOW §9 伏笔）、结构 proposal 脚本、agent / skill。
- 由日志驱动的 V08 自动化与参数校准。
- 近似算法升级（Fib、背离）。
- 执行时刻的检查（如用实际开盘价判 V13）。
- 行情缓存。

## 完成标准

- 只编辑档案文件、重复运行同一条管道，就能走完 ⑦ 的六个阶段。
- 执行器中不再有 `manual` / `todo` / `memo`；每个未知结果都对应一个带 key 的提问。
- 代码中不出现规则 ID；包 ≤ 2200 行；pytest 与 ruff 通过。

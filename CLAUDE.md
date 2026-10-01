# tradesys

把自然语言的投资哲学变成可执行的判断：**规则是数据（playbook），代码是工具，执行器是通用的。**

## 入口

| 文件 | 内容 |
| --- | --- |
| `docs/DESIGN.md` | 设计：四层、数据对象、rule 块语法、工具约定、边界 |
| `playbooks/technical.md` | 当前 playbook：自然语言规则 + rule 块（方法论 Source of Truth） |
| `docs/plans/phase-1.md` | 当前阶段计划 |
| `docs/sources/` | 原始材料：`voice/` 原文，`summaries/` LLM 整理 |
| `docs/archive/` | 已被取代的旧文档，仅供参考 |

## 开发守则

- **代码依赖规则**：规则、阈值只写在 playbook；代码中不出现任何规则 ID。换风格 = 换 playbook。
- **小工具 + 组合**：工具是纯函数 `tool(snap, **args) -> Check`，约 ≤ 50 行，在 `tradesys/tools/__init__.py` 注册。复杂判断靠在 rule 块里组合工具，不写全能函数。
- **执行器不含规则**：`tradesys/run.py` 只解析 rule 块并调用工具；只有 rule 块语法确实不够用时才改它。
- **编排可替换**：CLI 每个命令 JSON 进出、可单独调用，将来 agent / skill 用同一组命令。不写 agent 代码。
- **文档先行**：先写 playbook 条目和 rule 块，再补缺少的工具；工具 docstring 首行写原语 ID 与来源。
- **简单优先**：MVP 够用即可；结构由人在 YAML 中画，机器只判定；包约 ≤ 1500 行。
- 规则以 voice 原文为准；测试名写原始案例，规则案例通过真实 playbook 运行。

## 常用命令

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format .
uv run tradesys tools
uv run tradesys run playbooks/technical.md < snap.json
```

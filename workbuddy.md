# workbuddy.md — 本项目使用 WorkBuddy 的开发上下文

> 本文件用于麦当劳程序员创意开发大赛 WorkBuddy 联动奖励的核验，记录项目真实使用 WorkBuddy 开发的过程。
> 所有描述与仓库内的提交历史、代码注释一致，可对照 `git log` 查验。

## 一、项目是什么时候、怎么用 WorkBuddy 做出来的

- **开发时间**：2026-10-09（比赛开始）至 2026-10-13，全程在 WorkBuddy 桌面端完成。
- **开发方式**：项目以 **WorkBuddy Skill 形态交付**——`skills/mctrace/` 是 Skill 定义（自主工作流 + 入口脚本），`packages/`、`apps/` 是实现。开发调试闭环是「在 WorkBuddy 对话里描述需求 → AI 改代码 → 本地 Skill 入口直跑验证 → 截图自查」。
- **用到的 WorkBuddy 能力**：
  1. **连接器配置**：通过 `~/.workbuddy/mcp.json` 配置 `mcd-mcp`（麦当劳 MCP 数据通道）与 `mctrace-app`（本项目自带的 MCP App 界面服务器，stdio）；
  2. **Skill 开发与调试**：用 WorkBuddy 编写/调试 SKILL.md 与 scripts（`install.py` 幂等安装、`configure_connector.py` 自主写连接器、`run_trace.py` 三场景入口）；
  3. **MCP 工具直调**：开发期通过 WorkBuddy 的 MCP 通道直接调用麦当劳 MCP 只读工具做探测与验证（6 城市 30 门店的跨店价差实证即由此完成，脚本与原始返回在开发机留存，结论写入 `docs/CONTEST_PRICE_PROBE_2026-10-13.md`）；
  4. **本地 HTML 视觉自查**：用无头浏览器分片截图、逐片核对排版后才交付（`apps/detective/detective.html` 的接案台、警徽、三册案卷均经此流程）。

## 二、项目结构里与 WorkBuddy 相关的部分

| 路径 | 作用 |
|---|---|
| `skills/mctrace/SKILL.md` | WorkBuddy Skill 定义（含三条硬禁止：不绕过 MCP 工具、不硬编码推荐结果、不声称界面已展示） |
| `skills/mctrace/scripts/install.py` | 一键安装/升级/卸载到 `~/.workbuddy/`（幂等） |
| `skills/mctrace/scripts/configure_connector.py` | 自主写入 `mcd-mcp` 连接器配置 |
| `skills/mctrace/scripts/run_trace.py` | 三场景入口：点餐 / 积分盘点 / 麦探长巡查 |
| `packages/mcp_app/server.py` | MCP App 服务器（MCP Apps / SEP-1865，`ui://mctrace/live-story` 资源） |

## 三、核验要点（供官方对照）

- 仓库根 `.gitignore` 已排除 `token.txt` 等一切凭证文件；`mcp-config.example.json` 只含 `${MCD_MCP_TOKEN}` 环境变量占位符，无任何真实 Token；
- 所有演示数据来自对麦当劳 MCP 的真实只读调用，trace 样本（`examples/traces/*.json`）带 `traceId` 与时间戳，可复现；
- 参赛作品为独立开发，非麦当劳官方产品（见 `CONTEST_DECLARATION.md` 与 README 免责声明）。

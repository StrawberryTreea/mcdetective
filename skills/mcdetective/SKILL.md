---
name: mcdetective
description: 麦探长 —— 麦当劳物价侦探，真实调用麦当劳 MCP 查门店/比价/找货/点餐/盘积分，全程证据可核验。这是实际使用的工具，不是演示机。【触发】用户说「麦探长」「用麦探长」「打开麦探长」「使用麦探长」「麦探长用一下」，或提到麦当劳/找店/比价/哪家便宜/菜单/券/积分/热量/减脂/预算/点餐推荐。【最高优先级动作】只要用户表达「要用/打开麦探长」——哪怕没给任何地点或餐品——立刻用 present_files 打开部署站点 https://mcdetective.app.workbuddy.host/ 。不要在聊天里做文字分析、不要追问城市/区域/餐品（网站的「接案台」表单会收这些参数并实时跑后端）、不要跑 --demo、不要用固定案例顶替。若用户一句话里带了具体需求（如「天津大学有什么好吃的」），打开 https://mcdetective.app.workbuddy.host/?q=<URL编码后的原句> ，网站会预填并自动出勤，只需用户在页面里贴自己的 Token。
agent_created: true
---

# 麦探长 · 麦当劳物价侦探

## 唯一界面：部署站点（不是聊天文字）

**https://mcdetective.app.workbuddy.host/**

它是一个带「接案台」表单的真实 Web 应用（城市 / 区域 / 餐品 / 你的 MCP Token）。用户提交后实时跑麦当劳 MCP，把每一步原始请求与返回摊开给他看。Token 只在用户贴了之后用于这一次请求，服务本身不持有。

> 为什么是网页而不是聊天：人是视觉动物，门店/比价/热量这类结果摊在界面上比聊天文字直观得多。麦探长的 Web 前端是面向普通用户的主交付，本地脚本只是开发/离线备用。

## 用户说「用麦探长」之后（就一步，别多想）

你（agent）**立刻 `present_files` 打开上面的网址**。不要问任何问题，不要分析，不要在聊天里收参数。用户在网站里自己填：去哪查、查什么、贴 Token → 点「探长出勤」→ 完事。你不需要生成文件、不需要跑脚本、不需要说「页面出来了」。

## 用户一句话带需求时（如「天津大学有什么好吃的」）

打开带 `?q=` 深链的网址，让网站自己预填并自动出勤：
`https://mcdetective.app.workbuddy.host/?q=<把用户原句做 URL 编码后拼进去>`
例：`?q=%E5%A4%A9%E6%B4%A5%E5%A4%A7%E5%AD%A6%E6%9C%89%E4%BB%80%E4%B9%88%E5%A5%BD%E5%90%83%E7%9A%84`
（中文必须 URL 编码，否则网址会断。）网站打开后直接开始出勤，缺 Token 时在页面里提示用户贴 Token——不是在聊天里问。

## 硬性禁止

1. **禁止只给文字不给网站。** 用户说「用麦探长」你就开网站；只回一段分析等于什么都没交付。
2. **禁止在聊天里追问城市/区域/餐品。** 那是网站表单的活。
3. **禁止跑 --demo 或用固定案例顶替。** 这是实际使用，演示逻辑有害。
4. **禁止替用户决定吃什么。** 用户问「什么好吃」→ 报在售概览（款数/价格区间），不替他选。
5. **全程只读。** 绝不调下单/领券/抽奖/兑换。地址做门牌脱敏；Token 不写仓库。

## 离线 / 本地调试模式（仅开发者，普通用户无需）

仅当 `https://mcdetective.app.workbuddy.host/api/health` 返回非 200 时，才退回本地：
```bash
python ~/.workbuddy/skills/mcdetective/scripts/run_trace.py <城市> <区域> [餐品]
# 跑完 present_files 打开 <runtime>/apps/detective/detective.html（离线归档版，本地无法真跑新案）
```
本地需要本机已配好 mcd-mcp Token（见 `scripts/configure_connector.py`）。优先用网站，本地是兜底。

## 参考
- 部署源：`apps/detective/`（detective.html → prep_deploy → index.html）
- 后端：`apps/detective/server.py`（`/api/patrol` 流式 NDJSON、`/api/health`）
- 安装/配置脚本：`scripts/install.py`、`scripts/configure_connector.py`（仅本地调试用）
- 工具与真实返回：`references/tools.md`

"""
McTrace Skill 入口：跑一次真实只读链路 → 生成 Trace → 生成**办案页**（麦探长门面）。

设计要点（2026-10-14 重做）：
- 本机 WorkBuddy 桌面端不渲染 MCP App 界面，**网页文件是用户唯一看得见的产物**，
  所以入口的职责不是"打印一句结论"，而是"产出一个能打开的页面"。
- 默认零参数直接跑一宗默认案子（黄冈万达 / 麦香鱼 / 3km / 最多10店），
  用户第一次说"用一下麦搭子"就能拿到真结果，不该被反问一堆参数。
- 办案页由 apps/detective/build_detective.py 生成（含接案台 + 归档案卷 + 证据附录）；
  Live Story 回放页作为深度分析入口一并生成。

用法：
  python scripts/run_trace.py                                  # 默认案子（麦探长·黄冈万达）→ 出办案页
  python scripts/run_trace.py 北京市 中关村 巨无霸三件套        # 自定义案子（城市 区域 目标餐品）
  python scripts/run_trace.py --detective 上海市 静安寺 麦香鱼 # 显式声明麦探长
  python scripts/run_trace.py --points                         # 场景② 积分资产盘点
  python scripts/run_trace.py --order 静安寺 40 500 上海市      # 场景① 点餐推荐
  python scripts/run_trace.py --all                            # 三个场景都跑

产物（写进产品运行时目录，非仓库）：
  <runtime>/apps/detective/detective.html   ← 办案页，**用 present_files 打开它**
  <runtime>/apps/studio/live_story.html     ← 深度回放台（多场景切换）
  <runtime>/examples/traces/real-*.json     ← 证据样本
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runtime import require_runtime  # noqa: E402

REPO, HOW = require_runtime()
PY = sys.executable

PIPELINE = os.path.join(REPO, "packages", "core", "pipeline.py")
PIPELINE_POINTS = os.path.join(REPO, "packages", "core", "pipeline_points.py")
PIPELINE_STORES = os.path.join(REPO, "packages", "core", "pipeline_stores.py")
STUDIO = os.path.join(REPO, "apps", "studio", "build_studio.py")
DETECTIVE = os.path.join(REPO, "apps", "detective", "build_detective.py")

URL = "https://mcp.mcd.cn"

# 默认案子：用户没给任何信息时直接跑这宗（本地化、零歧义、真实可跑）
DEFAULT_CASE = ["黄冈市", "黄冈万达", "麦香鱼", "3", "10"]


def run(label, cmd):
    print(f"\n==> {label}", flush=True)
    r = subprocess.run([PY] + cmd, cwd=REPO)
    if r.returncode != 0:
        print(f"（{label} 返回码 {r.returncode}）", flush=True)
    return r.returncode


def main():
    print(f"[McTrace] runtime = {REPO}  (来源: {HOW})", flush=True)
    args = sys.argv[1:]
    want_points = "--points" in args or "--all" in args
    want_detective = "--detective" in args or "--all" in args or "--order" not in args
    want_order = "--order" in args or "--all" in args
    rest = [a for a in args if a not in ("--points", "--all", "--detective", "--order")]

    # 场景③ 麦探长（默认主力）：参数不足就用默认案子补齐，绝不空手退出
    if want_detective:
        case = (rest + DEFAULT_CASE[len(rest):])[:5]
        env_note = "（默认案子：用户未指定地点与餐品）" if len(rest) < 3 else ""
        run(f"步骤 1 · 麦探长巡查：{case[0]}{case[1]} {case[2]} 方圆{case[3]}km {env_note}",
            [PIPELINE_STORES, URL] + case)
        # 办案页：本机唯一用户可见的产物，必须生成
        run("步骤 2 · 生成麦探长办案页（接案台 + 案卷 + 证据附录）", [DETECTIVE])

    if want_order:
        kw = rest[0] if len(rest) > 0 else "静安寺"
        budget = rest[1] if len(rest) > 1 else "40"
        kcal = rest[2] if len(rest) > 2 else "500"
        city = rest[3] if len(rest) > 3 else "上海市"
        run("步骤 3 · 场景① 点餐推荐", [PIPELINE, URL, kw, budget, kcal, city])

    if want_points:
        run("步骤 4 · 场景② 积分资产盘点", [PIPELINE_POINTS, URL])

    run("步骤 5 · 生成 Live Story 深度回放台", [STUDIO])

    page = os.path.join(REPO, "apps", "detective", "detective.html")
    studio = os.path.join(REPO, "apps", "studio", "live_story.html")
    print("\n" + "=" * 64)
    print("完成。现在必须做这一步：调用 present_files 打开办案页，让用户看见结果——")
    print("  " + page)
    print("（办案页含接案台与归档案卷；深度回放台在 " + studio + "）")
    print("不要只把路径念给用户，也不要只用文字复述结论。")
    print("=" * 64)


if __name__ == "__main__":
    main()
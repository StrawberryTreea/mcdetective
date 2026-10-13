"""
McTrace Skill 入口：跑一次真实只读链路 → 生成 Trace → 生成可视化回放页。

前置：产品已安装（python install.py）。Token 从 ~/.workbuddy/mcp.json 或 <runtime>/token.txt 读取。

用法：
  python scripts/run_trace.py                          # 场景① 点餐（静安寺 / ¥40 / 500kcal）
  python scripts/run_trace.py 静安寺 40 500 上海市       # 场景① 自定义参数
  python scripts/run_trace.py --points                 # 场景② 积分资产盘点
  python scripts/run_trace.py --detective              # 场景③ 麦探长跨店比价（北京中关村 / 精选单人餐三件套 / 方圆3km / 最多10店）
  python scripts/run_trace.py --detective 北京市 中关村 巨无霸三件套 3 10   # 场景③ 自定义：城市 区域 目标餐品 半径km 最多店数
  python scripts/run_trace.py --all                    # 全部场景都跑

产物（写进产品运行时目录，非仓库）：
  <runtime>/examples/traces/real-*.json
  <runtime>/apps/studio/live_story.html   ← 用 present_files 打开它
"""
import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runtime import require_runtime  # noqa: E402

REPO, HOW = require_runtime()
PY = sys.executable

PIPELINE = os.path.join(REPO, "packages", "core", "pipeline.py")
PIPELINE_POINTS = os.path.join(REPO, "packages", "core", "pipeline_points.py")
PIPELINE_STORES = os.path.join(REPO, "packages", "core", "pipeline_stores.py")
STUDIO = os.path.join(REPO, "apps", "studio", "build_studio.py")

URL = "https://mcp.mcd.cn"


def run(label, cmd):
    print(f"\n==> {label}")
    r = subprocess.run([PY] + cmd, cwd=REPO)
    if r.returncode != 0:
        sys.exit(r.returncode)


def main():
    print(f"[McTrace] runtime = {REPO}  (来源: {HOW})")

    args = sys.argv[1:]
    want_points = "--points" in args or "--all" in args
    want_detective = "--detective" in args or "--all" in args
    want_order = ("--points" not in args and "--detective" not in args) or ("--all" in args)
    rest = [a for a in args if a not in ("--points", "--all", "--detective")]

    if want_order:
        kw = rest[0] if len(rest) > 0 else "静安寺"
        budget = rest[1] if len(rest) > 1 else "40"
        kcal = rest[2] if len(rest) > 2 else "500"
        city = rest[3] if len(rest) > 3 else "上海市"
        run("步骤 1 · 场景① 点餐推荐（真实只读链路）",
            [PIPELINE, URL, kw, budget, kcal, city])

    if want_points:
        run("步骤 2 · 场景② 积分资产盘点（真实只读链路）",
            [PIPELINE_POINTS, URL])

    if want_detective:
        d_city = rest[0] if len(rest) > 0 else "北京市"
        d_kw = rest[1] if len(rest) > 1 else "中关村"
        d_target = rest[2] if len(rest) > 2 else "精选单人餐三件套"
        d_radius = rest[3] if len(rest) > 3 else "3"
        d_n = rest[4] if len(rest) > 4 else "10"
        run("步骤 · 场景③ 麦探长跨店比价巡查（真实只读链路）",
            [PIPELINE_STORES, URL, d_city, d_kw, d_target, d_radius, d_n])

    run("步骤 3 · 生成 Live Story 回放页", [STUDIO])

    page = os.path.join(REPO, "apps", "studio", "live_story.html")
    print("\n" + "=" * 60)
    print("完成。请用 present_files 打开回放页：")
    print("  " + page)
    print("（顶部下拉可切换场景；点任意实体可看原始 request/response 证据）")
    print("=" * 60)


if __name__ == "__main__":
    main()

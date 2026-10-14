"""
McTrace · 一键安装器（把产品装进 WorkBuddy 智能体）

安装两处，互不干扰：
  ~/.workbuddy/apps/mcdetective/    产品运行时（packages / apps / examples / VERSION）
  ~/.workbuddy/skills/mcdetective/  智能体入口（SKILL.md / scripts / references）

用法：
  python skills/mcdetective/scripts/install.py                # 安装或升级（幂等）
  python skills/mcdetective/scripts/install.py --source <dir> # 从指定源码目录安装
  python skills/mcdetective/scripts/install.py --check        # 只检查安装状态
  python skills/mcdetective/scripts/install.py --uninstall    # 卸载（移入 ~/.workbuddy/trash/，不直接删）

幂等说明：packages / apps / examples 一律「覆盖同步」，
但 runtime 根下已存在的 token.txt 等个人文件不会被删除。
"""
import os
import sys
import time
import shutil
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runtime import (  # noqa: E402
    WB_HOME, SKILL_DIR, INSTALLED_RUNTIME, INSTALLED_SKILL
)

SKIP_DIRS = {"__pycache__", ".git", "raw", ".ipynb_checkpoints"}
SKIP_FILES = {".DS_Store"}


def repo_root_from_here():
    # SKILL_DIR = <repo>/skills/mcdetective  →  <repo>
    return os.path.normpath(os.path.join(SKILL_DIR, "..", ".."))


def sync_dir(src, dst):
    """覆盖同步目录：保留目标端已有个人文件，覆盖同名代码文件。"""
    if not os.path.isdir(src):
        return 0
    os.makedirs(dst, exist_ok=True)
    n = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(root, src)
        target_root = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target_root, exist_ok=True)
        for f in files:
            if f in SKIP_FILES:
                continue
            s = os.path.join(root, f)
            t = os.path.join(target_root, f)
            shutil.copy2(s, t)
            n += 1
    return n


def check_status():
    print("== McTrace 安装状态 ==")
    print(f"  运行时  {INSTALLED_RUNTIME}  {'✅ 已安装' if os.path.isdir(INSTALLED_RUNTIME) else '❌ 未安装'}")
    print(f"  技能    {INSTALLED_SKILL}  {'✅ 已安装' if os.path.isdir(INSTALLED_SKILL) else '❌ 未安装'}")
    mcp = os.path.join(WB_HOME, "mcp.json")
    servers = {}
    if os.path.exists(mcp):
        try:
            import json as _j
            servers = (_j.load(open(mcp, encoding="utf-8")) or {}).get("mcpServers") or {}
        except Exception:
            servers = {}

    def mark(ok, msg_ok, msg_no):
        return ("✅ " + msg_ok) if ok else ("❌ " + msg_no)

    srv = servers.get("mcd-mcp")
    ready_mcd = bool(srv) and "${MCD_TOKEN}" not in ((srv.get("headers") or {}).get("Authorization", ""))
    print(f"  数据通道 {mcp}  {mark(ready_mcd, 'mcd-mcp 已配置', 'mcd-mcp 未配置')}")

    app_py = (app.get("args") or [""])[0] if app else ""
    ready_app = bool(app_py) and os.path.exists(app_py)

    tok = os.path.join(INSTALLED_RUNTIME, "token.txt")
    print(f"  本机凭据 {tok}  {'✅ 存在' if os.path.exists(tok) else '（可选）'}")


def do_uninstall():
    trash = os.path.join(WB_HOME, "trash", "mcdetective-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(trash, exist_ok=True)
    moved = []
    for name, path in (("runtime", INSTALLED_RUNTIME), ("skill", INSTALLED_SKILL)):
        if os.path.exists(path):
            dst = os.path.join(trash, name)
            shutil.move(path, dst)
            moved.append(f"{path}  →  {dst}")
    if not moved:
        print("本机没有安装 McTrace，无需卸载。")
        return
    print("已卸载（未删除任何文件，全部移入回收目录）：")
    for m in moved:
        print("  " + m)


PULL_ITEMS = [
    ("examples", "traces"),
    ("apps", "studio", "live_story.html"),
    ("packages", "mcp_app", "assets"),
    ("docs",),
]


def pull_artifacts(src):
    """把运行时里的最新产物（Trace + 回放页 + 落地页）回写到源码仓库，保持样例最新。"""
    n = 0
    for parts in PULL_ITEMS:
        s = os.path.join(INSTALLED_RUNTIME, *parts)
        t = os.path.join(src, *parts)
        if os.path.isdir(s):
            n += sync_dir(s, t)
        elif os.path.isfile(s):
            os.makedirs(os.path.dirname(t), exist_ok=True)
            shutil.copy2(s, t)
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=None, help="源码仓库目录（默认：本脚本所在的仓库）")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--pull", action="store_true", help="把运行时产物回流到源码仓库")
    args = ap.parse_args()

    if args.check:
        check_status()
        return
    if args.uninstall:
        do_uninstall()
        return

    src = args.source or repo_root_from_here()

    if args.pull:
        n = pull_artifacts(src)
        print(f"✅ 已把 {n} 个产物从 {INSTALLED_RUNTIME} 回写到 {src}")
        return

    if not os.path.isdir(os.path.join(src, "packages", "core")):
        raise SystemExit(f"[麦探长] 源码目录无效：{src}（未找到 packages/core）。"
                         f"\n  若在别的位置，请用 --source <dir> 指定。")

    print(f"[麦探长] 源码：{src}")
    total = 0
    # 1) 运行时
    for sub in ("packages", "apps", "examples"):
        n = sync_dir(os.path.join(src, sub), os.path.join(INSTALLED_RUNTIME, sub))
        print(f"  运行时 · {sub:<9} 同步 {n} 个文件")
        total += n
    # trace 输出目录必须存在
    os.makedirs(os.path.join(INSTALLED_RUNTIME, "examples", "traces"), exist_ok=True)

    # 2) 技能入口
    n_skill = sync_dir(os.path.join(src, "skills", "mcdetective"), INSTALLED_SKILL)
    print(f"  技能    · 入口      同步 {n_skill} 个文件")
    total += n_skill

    # 3) 版本号
    ver = os.path.join(INSTALLED_RUNTIME, "VERSION")
    with open(ver, "w", encoding="utf-8") as f:
        f.write("mcdetective 1.0.0\n" + time.strftime("installed %Y-%m-%d %H:%M:%S") + "\n")

    print(f"\n✅ 安装完成，共同步 {total} 个文件。")
    print(f"   运行时：{INSTALLED_RUNTIME}")
    print(f"   技能入口：{INSTALLED_SKILL}")

    # 收尾：按 Connector / Token 现状给不同提示
    mcp_cfg = os.path.join(WB_HOME, "mcp.json")
    ready = False
    try:
        if os.path.exists(mcp_cfg):
            import json as _j
            _servers = ((_j.load(open(mcp_cfg, encoding="utf-8")) or {}).get("mcpServers") or {})
            _srv = _servers.get("mcd-mcp") or {}
            ready = (bool(_srv) and "${MCD_TOKEN}" not in ((_srv.get("headers") or {}).get("Authorization", ""))
                     and bool(_app))
    except Exception:
        pass

    if ready:
        print("   重启 WorkBuddy 后，对话里直接说：")
        print("   「帮我在黄冈万达附近点份减脂晚餐，50元以内」\n   就会直接给你结论 + 每一步的证据（纯文字，不需要点任何按钮）。")
    else:
        print("\n下一步（注册连接器；数据通道需要一次 Token）：")
        print(f"   python {os.path.join(INSTALLED_SKILL, 'scripts', 'configure_connector.py')} --token <Token>")
        print("   完成后重启 WorkBuddy 让连接器生效。")


if __name__ == "__main__":
    main()

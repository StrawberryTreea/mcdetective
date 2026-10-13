"""
McTrace · 连接器自主配置脚本（供 Skill / 模型调用）

往 WorkBuddy 的 MCP 配置（~/.workbuddy/mcp.json）里注册两个服务器：

  mcd-mcp       数据通道：麦当劳官方 MCP（含用户自己的 Token）
  mctrace-app   应用本体：本机 McTrace MCP 服务器（stdio），提供对话内的 Live Story 界面

幂等：已存在则不覆盖；--force 可替换；其他服务器配置原样保留。

用法：
  python scripts/configure_connector.py --check
  python scripts/configure_connector.py --token <Token>
  python scripts/configure_connector.py --token-file <文件>      # 推荐，避免 Token 进命令行历史
  python scripts/configure_connector.py --server mctrace         # 只注册应用本体（不需要 Token）
  python scripts/configure_connector.py --token <Token> --force

Token 只写入当前用户本机的 ~/.workbuddy/mcp.json（个人配置），不进仓库、不上报。
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runtime import WB_HOME, INSTALLED_RUNTIME, _repo_root  # noqa: E402

WB_MCP = os.path.join(WB_HOME, "mcp.json")
PLACEHOLDER = "${MCD_TOKEN}"
MCD_SERVER = {
    "type": "streamablehttp",
    "url": "https://mcp.mcd.cn",
    "headers": {"Authorization": "Bearer " + PLACEHOLDER},
}


def default_python():
    return sys.executable


def server_py():
    """优先用装机运行时里的 server.py，没有则退回源码仓库。"""
    installed = os.path.join(INSTALLED_RUNTIME, "packages", "mcp_app", "server.py")
    if os.path.exists(installed):
        return installed
    return os.path.join(_repo_root(), "packages", "mcp_app", "server.py")


def mctrace_entry(python_path):
    return {"command": python_path, "args": [server_py()]}


def read_token(args):
    if args.token:
        return args.token.strip(), "--token"
    env = os.environ.get("MCD_TOKEN")
    if env:
        return env.strip(), "MCD_TOKEN"
    if args.token_file and os.path.exists(args.token_file):
        return open(args.token_file, encoding="utf-8").read().strip(), args.token_file
    local = os.path.join(INSTALLED_RUNTIME, "token.txt")
    if os.path.exists(local):
        return open(local, encoding="utf-8").read().strip(), local
    env_file = os.environ.get("MCD_TOKEN_FILE")
    if env_file and os.path.exists(env_file):
        return open(env_file, encoding="utf-8").read().strip(), env_file
    return None, None


def load_cfg():
    cfg = {}
    if os.path.exists(WB_MCP):
        try:
            cfg = json.load(open(WB_MCP, encoding="utf-8")) or {}
        except Exception:
            cfg = {}
    return cfg


def check_only(level="both"):
    cfg = load_cfg()
    servers = cfg.get("mcpServers") or {}

    lines = []
    ready = True
    srv = servers.get("mcd-mcp")
    if not srv:
        lines.append("❌ 未注册 mcd-mcp（麦当劳 MCP 数据通道）")
        ready = False
    else:
        auth = (srv.get("headers") or {}).get("Authorization", "")
        ok = bool(auth) and PLACEHOLDER not in auth
        lines.append(("✅ mcd-mcp 已注册，Token 就绪" if ok else "⚠ mcd-mcp 已注册但 Token 未填充"))
        ready = ready and ok

    app = servers.get("mctrace-app")
    if level in ("both", "mctrace"):
        if not app:
            lines.append("❌ 未注册 mctrace-app（对话内 Live Story 界面）")
            ready = False
        else:
            sp = (app.get("args") or [""])[0]
            ok = os.path.exists(sp)
            lines.append(("✅ mctrace-app 已注册，入口存在" if ok
                          else "⚠ mctrace-app 已注册但入口不存在：" + sp))
            ready = ready and ok

    print("== 连接器状态 ==")
    for l in lines:
        print("  " + l)
    sys.exit(0 if ready else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=None)
    ap.add_argument("--token-file", default=None)
    ap.add_argument("--force", action="store_true", help="已存在时用新 Token 覆盖")
    ap.add_argument("--check", action="store_true", help="只检查配置状态")
    ap.add_argument("--server", default="both", choices=["both", "mcd", "mctrace"],
                    help="注册哪个服务器（默认两个）")
    ap.add_argument("--python", default=None, help="运行 mctrace-app 的 Python 解释器路径")
    args = ap.parse_args()

    if args.check:
        check_only("both")

    cfg = load_cfg()
    servers = cfg.get("mcpServers") or {}
    changed = []

    # ---------- 数据通道：麦当劳 MCP ----------
    if args.server in ("both", "mcd"):
        existing = servers.get("mcd-mcp")
        need_write = True
        if existing and not args.force:
            auth = (existing.get("headers") or {}).get("Authorization", "")
            if auth and PLACEHOLDER not in auth:
                print("OK: mcd-mcp 已存在且 Token 就绪，跳过。")
                need_write = False
        if need_write:
            token, src = read_token(args)
            if not token:
                print("NEED_TOKEN: 未提供麦当劳 MCP Token。")
                print("  请向用户索取其麦当劳 MCP Token，然后运行：")
                print("  python scripts/configure_connector.py --token <Token>")
                sys.exit(2)
            srv = dict(MCD_SERVER)
            srv["headers"] = {"Authorization": "Bearer " + token}
            servers["mcd-mcp"] = srv
            changed.append("mcd-mcp（Token 来源：%s）" % src)

    # ---------- 应用本体：McTrace MCP App ----------
    if args.server in ("both", "mctrace"):
        existing = servers.get("mctrace-app")
        if existing and not args.force:
            print("OK: mctrace-app 已存在，跳过。")
        else:
            servers["mctrace-app"] = mctrace_entry(args.python or default_python())
            changed.append("mctrace-app（stdio：%s）" % server_py())

    if not changed:
        return

    cfg["mcpServers"] = servers
    os.makedirs(os.path.dirname(WB_MCP), exist_ok=True)
    with open(WB_MCP, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    print("OK: 已写入 ~/.workbuddy/mcp.json")
    for c in changed:
        print("   + " + c)
    if "mctrace-app" in " ".join(changed):
        print("   对话里会出现带界面的 mctrace-scan-order / mctrace-scan-points 工具。")
    print("   提示：首次写入后需重启 WorkBuddy 让连接器生效。")


if __name__ == "__main__":
    main()

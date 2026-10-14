# -*- coding: utf-8 -*-
"""组装部署目录（办案服务版）：把运行时源码 + 页面 + 归档案卷拷进发布目录。

教训（2026-10-14）：之前只拷 detective.html 忘了覆盖 index.html，
线上跑了一个版本的旧 JS（解析器里还有「缺餐品默认巨无霸」的逻辑）。
本脚本固定 detective.html → index.html，并在结束时校验。

用法：
    python scripts/prep_deploy.py [目标目录]
"""
import os
import shutil
import sys

RUNTIME = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
DEFAULT_OUT = r"C:/Users/xiaoz/Desktop/2026-10-麦麦MCP/.workbuddy/scratch/2026-10-13_site"


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    os.makedirs(out, exist_ok=True)
    for sub in ("packages/core", "examples/traces"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    # 页面：detective.html → index.html（服务只伺服 index.html）
    shutil.copy2(os.path.join(RUNTIME, "apps/detective/detective.html"),
                 os.path.join(out, "index.html"))
    for f in ("server.py", "case_render.py"):
        shutil.copy2(os.path.join(RUNTIME, "apps/detective", f), os.path.join(out, f))
    for f in ("mcp_client.py", "pipeline_stores.py"):
        shutil.copy2(os.path.join(RUNTIME, "packages/core", f), os.path.join(out, "packages/core", f))
    src_traces = os.path.join(RUNTIME, "examples/traces")
    for f in os.listdir(src_traces):
        if f.startswith("real-detective-"):
            shutil.copy2(os.path.join(src_traces, f), os.path.join(out, "examples/traces", f))

    # 校验：index.html 必须与 detective.html 一致（防再次漏覆盖）
    import filecmp
    same = filecmp.cmp(os.path.join(out, "index.html"),
                       os.path.join(RUNTIME, "apps/detective/detective.html"), shallow=False)
    print(f"部署目录已组装：{out}")
    print(f"  index.html 与 detective.html 一致：{'✓' if same else '✗ 不一致！'}")
    if not same:
        sys.exit(1)
    print("  文件：" + ", ".join(sorted(
        os.path.relpath(os.path.join(dp, f), out).replace("\\", "/")
        for dp, _, fs in os.walk(out) for f in fs)))


if __name__ == "__main__":
    main()
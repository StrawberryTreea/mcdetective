"""
麦探长 · runtime 定位（同时支持「安装布局」与「仓库布局」）

安装布局：
  ~/.workbuddy/apps/mcdetective/      ← runtime（packages / apps / examples）
  ~/.workbuddy/skills/mcdetective/    ← skill（SKILL.md / scripts / references）

仓库布局（开发时）：
  <repo>/packages / apps / examples
  <repo>/skills/mcdetective/scripts/…  ← 本文件

解析优先级：环境变量 MCDETECTIVE_HOME  →  安装目录  →  仓库相对路径
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
WB_HOME = os.path.join(os.path.expanduser("~"), ".workbuddy")
INSTALLED_RUNTIME = os.path.join(WB_HOME, "apps", "mcdetective")
INSTALLED_SKILL = os.path.join(WB_HOME, "skills", "mcdetective")


def _repo_root():
    # skills/mcdetective  →  <repo>
    return os.path.normpath(os.path.join(SKILL_DIR, "..", ".."))


def resolve_runtime():
    """返回 (runtime_dir, how)；未找到时 (None, 'notfound')"""
    env_home = os.environ.get("MCDETECTIVE_HOME")
    if env_home and os.path.isdir(env_home):
        return os.path.abspath(env_home), "MCDETECTIVE_HOME"

    if os.path.isdir(INSTALLED_RUNTIME):
        return INSTALLED_RUNTIME, "installed"

    repo = _repo_root()
    if os.path.isdir(os.path.join(repo, "packages", "core")):
        return repo, "repo"

    return None, "notfound"


def require_runtime():
    rt, how = resolve_runtime()
    if not rt:
        raise SystemExit(
            "[麦探长] 未找到产品运行时。请先安装：\n"
            "  python <repo>/skills/mcdetective/scripts/install.py\n"
            "或设置环境变量 MCDETECTIVE_HOME 指向含 packages/ 的目录。"
        )
    return rt, how


def py():
    import sys
    return sys.executable

"""model_switch.py 宿主分发：codex 子命令转发给 Codex 后端；缺省仍为 Claude。"""
import os
import subprocess
import sys

_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "model-switch", "scripts",
)
MODEL_SWITCH = os.path.join(_SCRIPTS, "model_switch.py")


def run_model_switch(args):
    return subprocess.run(
        [sys.executable, MODEL_SWITCH] + args,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def test_codex_subcommand_dispatches(tmp_path):
    r = run_model_switch(["codex", "list", "--codex-home", str(tmp_path)])
    assert r.returncode == 0, r.stderr
    assert "尚未定义任何提供商" in r.stdout


def test_default_host_is_claude(tmp_path):
    r = run_model_switch(["list",
                          "--profiles", str(tmp_path / "nope-profiles.json"),
                          "--settings", str(tmp_path / "nope-settings.json")])
    assert r.returncode == 1, r.stdout
    assert "找不到" in r.stderr

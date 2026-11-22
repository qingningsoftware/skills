"""Claude 侧 switch official：切回官方登录 = 移除脚本管理的 5 个 env 变量，其余保留。"""
import json
import os
import sys

_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "model-switch", "scripts",
)
sys.path.insert(0, _SCRIPTS)

SETTINGS = {
    "env": {
        "ANTHROPIC_BASE_URL": "https://a.b/c",
        "ANTHROPIC_AUTH_TOKEN": "sk-x",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "m1",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "m2",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "m3",
        "OTHER_VAR": "keep-me",
    },
    "model": "sonnet",
}


def _args(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(SETTINGS), encoding="utf-8")
    ns = type("A", (), {"settings": str(settings),
                        "profiles": str(tmp_path / "nope-profiles.json"),
                        "key": "official"})()
    return ns, settings


def test_claude_switch_official_removes_managed_vars(tmp_path):
    import model_switch as ms
    ns, settings = _args(tmp_path)
    rc = ms.cmd_switch(ns)
    assert rc == 0
    env = json.loads(settings.read_text(encoding="utf-8"))["env"]
    for var in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
                "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL"):
        assert var not in env
    assert env["OTHER_VAR"] == "keep-me"  # 无关变量保留
    assert json.loads(settings.read_text(encoding="utf-8"))["model"] == "sonnet"
    assert (settings.parent / "settings.json.bak-model-switch").exists()


def test_claude_switch_official_needs_no_profiles(tmp_path):
    # profiles 文件不存在也能切回官方（load_json 不会再因 profiles 缺失退出）
    import model_switch as ms
    ns, settings = _args(tmp_path)
    assert ms.cmd_switch(ns) == 0


def test_claude_add_rejects_official_key(tmp_path):
    import model_switch as ms, pytest
    profiles = tmp_path / "model-profiles.json"
    profiles.write_text("{}", encoding="utf-8")
    ns = type("A", (), {"key": "official", "name": "x",
                        "base_url": "https://a.b/c", "token": "t",
                        "profiles": str(profiles), "force": False})()
    with pytest.raises(SystemExit):
        ms.cmd_add(ns)

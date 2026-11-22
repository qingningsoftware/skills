"""codex_switch 测试。SAMPLE 锚定真实 ~/.codex/config.toml 的形态（单引号 literal string 等）。"""

SAMPLE = '''model = "gpt-5.6-terra"
model_reasoning_effort = "medium"

[projects.'d:\\work\\iptv\\src']
trust_level = "trusted"

[windows]
sandbox = "elevated"
'''


def test_parse_and_get_current():
    import codex_switch as cs
    cfg = cs.parse_config(SAMPLE)
    assert cs.get_current(cfg) == ("gpt-5.6-terra", None)
    assert cs.list_providers(cfg) == {}


def test_default_codex_home(monkeypatch, tmp_path):
    import codex_switch as cs
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    assert cs.default_codex_home() == str(tmp_path)
    monkeypatch.delenv("CODEX_HOME")
    assert cs.default_codex_home().endswith(".codex")


def test_load_config_text_missing_returns_empty(tmp_path):
    import codex_switch as cs
    assert cs.load_config_text(str(tmp_path / "nope.toml")) == ""


def test_set_provider_insert_and_replace():
    import codex_switch as cs
    t1 = cs.set_current_provider(SAMPLE, "glm")
    assert 'model_provider = "glm"' in t1
    assert t1.index("model_provider") < t1.index("[projects.")
    t2 = cs.set_current_provider(t1, "qwen")
    assert 'model_provider = "qwen"' in t2 and t2.count("model_provider =") == 1
    t3 = cs.set_current_provider(t2, None)
    assert "model_provider" not in t3


def test_set_provider_model_line_and_model_reasoning_untouched():
    import codex_switch as cs
    t = cs.set_current_provider(SAMPLE, "glm", model="glm-4.7")
    assert 'model = "glm-4.7"' in t and 'model_reasoning_effort = "medium"' in t


def test_upsert_section_preserves_literal_strings():
    import codex_switch as cs
    t = cs.upsert_provider_section(SAMPLE, "glm", {
        "name": "GLM 测试", "base_url": "https://provider.example.com/api/v4",
        "env_key": "GLM_API_KEY", "wire_api": "chat"})
    cfg = cs.parse_config(t)
    assert cfg["model_providers"]["glm"]["env_key"] == "GLM_API_KEY"
    assert "[projects.'d:\\work\\iptv\\src']" in t
    t2 = cs.upsert_provider_section(t, "glm", {"name": "x", "base_url": "https://a.b/c",
                                               "env_key": "GLM_API_KEY", "wire_api": "responses"})
    assert cs.parse_config(t2)["model_providers"]["glm"]["wire_api"] == "responses"
    assert t2.count("[model_providers.glm]") == 1


def test_backup_first_run_and_subsequent(tmp_path):
    import codex_switch as cs, json, os
    home = tmp_path; (home / "config.toml").write_text(SAMPLE, encoding="utf-8")
    (home / "auth.json").write_text("{}", encoding="utf-8")
    cfg = cs.parse_config(SAMPLE)
    d1 = cs.backup_before_write(str(home), cfg, reader=lambda n: None)
    assert (d1 / "..").resolve() == home.resolve()
    assert json.loads((d1 / "env-snapshot.json").read_text(encoding="utf-8")) == {}
    assert (d1 / "config.toml").exists() and (d1 / "auth.json").exists()
    d2 = cs.backup_before_write(str(home), cfg, reader=lambda n: None)
    assert d1 == d2  # 之后追加到同一目录
    assert any(p.name.startswith("config.toml.bak-") for p in d2.iterdir())


def test_modify_config_rejects_invalid_toml_without_writing(tmp_path):
    import codex_switch as cs
    p = tmp_path / "config.toml"; p.write_text(SAMPLE, encoding="utf-8")
    before = p.read_text(encoding="utf-8")
    try:
        cs.modify_config(str(p), "not = [valid", str(tmp_path), reader=lambda n: None)
        assert False, "应当退出"
    except SystemExit:
        pass
    assert p.read_text(encoding="utf-8") == before  # 未落盘


def test_switch_cmd_end_to_end(tmp_path, capsys):
    import codex_switch as cs
    home = tmp_path; (home / "config.toml").write_text(SAMPLE, encoding="utf-8")
    text = cs.upsert_provider_section(SAMPLE, "glm", {"name": "GLM", "base_url": "https://a.b/c",
                                                      "env_key": "GLM_API_KEY", "wire_api": "chat"})
    (home / "config.toml").write_text(text, encoding="utf-8")
    rc = cs.cmd_switch(type("A", (), {"key": "glm", "model": "glm-4.7",
                                      "codex_home": str(home)})())
    assert rc == 0
    cfg = cs.parse_config((home / "config.toml").read_text(encoding="utf-8"))
    assert cfg["model_provider"] == "glm" and cfg["model"] == "glm-4.7"
    assert "[projects.'d:\\work\\iptv\\src']" in (home / "config.toml").read_text(encoding="utf-8")
    assert "重启" in capsys.readouterr().out  # 切换后必须提示重启 Codex


def test_switch_official_removes_provider_line(tmp_path):
    import codex_switch as cs
    home = tmp_path
    t = cs.set_current_provider(SAMPLE, "glm")
    (home / "config.toml").write_text(t, encoding="utf-8")
    cs.cmd_switch(type("A", (), {"key": "official", "model": None,
                                 "codex_home": str(home)})())
    cfg = cs.parse_config((home / "config.toml").read_text(encoding="utf-8"))
    assert "model_provider" not in cfg


def test_switch_unknown_key_exits(tmp_path):
    import codex_switch as cs, pytest
    home = tmp_path; (home / "config.toml").write_text(SAMPLE, encoding="utf-8")
    with pytest.raises(SystemExit):
        cs.cmd_switch(type("A", (), {"key": "nope", "model": None,
                                     "codex_home": str(home)})())


def test_add_cmd_appends_section_and_sets_var(tmp_path, capsys):
    import codex_switch as cs
    home = tmp_path; (home / "config.toml").write_text(SAMPLE, encoding="utf-8")
    setter_calls = []
    rc = cs.cmd_add(type("A", (), {"key": "glm", "name": "智谱", "base_url": "https://a.b/c",
        "env_key": "GLM_API_KEY", "wire_api": None, "set_env_var": "sk-test123",
        "force": False, "force_env": False, "codex_home": str(home),
        })(), setter=lambda n, v: setter_calls.append((n, v)), reader=lambda n: None)
    assert rc == 0
    cfg = cs.parse_config((home / "config.toml").read_text(encoding="utf-8"))
    assert cfg["model_providers"]["glm"]["wire_api"] == "chat"  # 缺省 chat
    assert setter_calls == [("GLM_API_KEY", "sk-test123")]


def test_add_refuses_existing_env_var_without_force_env(tmp_path):
    import codex_switch as cs, pytest
    home = tmp_path; (home / "config.toml").write_text(SAMPLE, encoding="utf-8")
    with pytest.raises(SystemExit):
        cs.cmd_add(type("A", (), {"key": "glm", "name": "x", "base_url": "https://a.b/c",
            "env_key": "GLM_API_KEY", "wire_api": "chat", "set_env_var": "v",
            "force": False, "force_env": False, "codex_home": str(home),
            })(), setter=lambda n, v: None, reader=lambda n: "already-set")


def test_list_and_status(tmp_path, capsys):
    import codex_switch as cs
    home = tmp_path
    t = cs.upsert_provider_section(SAMPLE, "glm", {"name": "GLM", "base_url": "https://a.b/c",
                                                   "env_key": "GLM_API_KEY", "wire_api": "chat"})
    (home / "config.toml").write_text(t, encoding="utf-8")
    args = type("A", (), {"codex_home": str(home)})()
    assert cs.cmd_list(args) == 0
    assert "glm" in capsys.readouterr().out
    assert cs.cmd_status(args) == 0
    assert "OpenAI 官方" in capsys.readouterr().out  # model_provider 不存在时


def test_bom_config_switch(tmp_path):
    # 记事本"UTF-8 with BOM"保存过的 config.toml 必须照常工作
    import codex_switch as cs
    home = tmp_path
    text = cs.upsert_provider_section(SAMPLE, "glm", {"name": "GLM", "base_url": "https://a.b/c",
                                                      "env_key": "GLM_API_KEY", "wire_api": "chat"})
    (home / "config.toml").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    rc = cs.cmd_switch(type("A", (), {"key": "glm", "model": None,
                                      "codex_home": str(home)})())
    assert rc == 0
    cfg = cs.parse_config((home / "config.toml").read_text(encoding="utf-8"))
    assert cfg["model_provider"] == "glm"


def test_add_rejects_official_key(tmp_path):
    # official 是 switch 的保留 key，add 不允许占用，否则 switch official 语义被劫持
    import codex_switch as cs, pytest
    home = tmp_path; (home / "config.toml").write_text(SAMPLE, encoding="utf-8")
    with pytest.raises(SystemExit):
        cs.cmd_add(type("A", (), {"key": "official", "name": "x", "base_url": "https://a.b/c",
            "env_key": "K", "wire_api": "chat", "set_env_var": None,
            "force": False, "force_env": False, "codex_home": str(home),
            })(), reader=lambda n: None)

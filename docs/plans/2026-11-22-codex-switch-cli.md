# codex-switch 独立 CLI 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现零模型依赖的 Codex 提供商切换 CLI（`codex-switch/codex_switch.py`），list/status/switch/add 四命令，直接读写 `~/.codex/config.toml`。

**Architecture:** 单文件 Python CLI，风格复用 `model-switch/skills/model-switch/scripts/model_switch.py`（out/err/mask、UTF-8 重配置、argparse）。对 config.toml 只做文本精准编辑（顶层 `model`/`model_provider` 两行 + `[model_providers.*]` 小节增改），tomllib 只用于读取与改后语法校验；任何修改前先备份，写入用临时文件+`os.replace` 原子替换。

**Tech Stack:** Python 3.11+ 仅标准库（tomllib、winreg、argparse、json、os、re、shutil、subprocess、sys、tempfile）；测试用 pytest。

**Spec:** `docs/specs/2026-11-21-codex-model-switch-design.md`（2026-11-22 定案版）

## Global Constraints

- Python 3.11+（tomllib）；运行时零第三方依赖；pytest 仅用于测试。
- 单文件 `codex-switch/codex_switch.py`；注释与输出全中文；复用 model_switch.py 的 `out/err/mask` 与 stdout/stderr UTF-8 reconfigure 写法。
- 禁止整文件重序列化：config.toml 只能文本精准编辑，注释与既有小节必须逐字节保留；tomllib 只读 + 改后校验。
- switch 永不写环境变量；任何 config.toml 修改前必须先备份（首次运行全量快照，此后时间戳副本）。
- 提交由用户本人执行：执行者完成每个任务后**只打印**该任务的 commit 命令，不运行 git commit。提交信息中文冒号前缀（如 `codex-switch：...`），结尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 测试不碰真实注册表与真实 `~/.codex`：env 读取器/写入器以参数注入，codex_home 一律用 tmp_path。

## Review Focus

1. `model_reasoning_effort` 等顶层键被误当 `model` 行改写 → 应只动 `model`/`model_provider` 两行（Task 2 测试 pin）。
2. 现有小节里的 `\\?\` 前缀、单引号 literal string（如 `[projects.'d:\work\iptv\src']`）被编辑破坏 → 应逐字节保留（Task 2、Task 4 测试 pin）。
3. `setx` 后进程环境过期，导致"变量已设"判断或 env 快照失真 → 应读注册表 HKCU\Environment 真值，进程环境只作后备（Task 3 测试 pin）。
4. 写入中途失败留下半截 config.toml 或非法 TOML 落盘 → 应先在内存校验、临时文件+`os.replace`，校验失败完全不写（Task 3 测试 pin）。
5. 切换后 Codex 仍在用旧配置的困惑 → 每次 switch 输出必须含"完全退出（含托盘）并重启 Codex"提示（Task 4 测试 pin）。

---

### Task 1: 脚手架与配置读取

**Files:**
- Create: `codex-switch/codex_switch.py`
- Create: `codex-switch/tests/conftest.py`
- Create: `codex-switch/tests/test_codex_switch.py`

**Interfaces:**
- Consumes: 无（首个任务）
- Produces:
  - `default_codex_home() -> str`（`CODEX_HOME` 环境变量优先，否则 `~/.codex`）
  - `load_config_text(path: str) -> str`（文件不存在返回 `""`）
  - `parse_config(text: str) -> dict`（`tomllib.loads`；空串→`{}`；解析失败→`err`+`sys.exit(1)`）
  - `get_current(cfg: dict) -> tuple[str | None, str | None]`（返回 `(model, model_provider)`）
  - `list_providers(cfg: dict) -> dict[str, dict]`（`cfg.get("model_providers", {})`）
  - `out(*args)` / `err(*args)` / `mask(token: str) -> str`（与 model_switch.py 相同语义）

- [ ] **Step 1: 环境检查**

Run: `python --version && python -m pytest --version`
Expected: Python ≥ 3.11；pytest 已装（未装则 `python -m pip install pytest`）

- [ ] **Step 2: 写 conftest.py 与失败测试**

`codex-switch/tests/conftest.py`（两行：把 `codex-switch/` 目录加入 `sys.path`）。测试样例 TOML 锚定真实文件形态：

```python
SAMPLE = '''model = "gpt-5.6-terra"
model_reasoning_effort = "medium"

[projects.'d:\\work\\iptv\\src']
trust_level = "trusted"

[windows]
sandbox = "elevated"
'''

def test_parse_and_get_current():
    import codex_switch as cs
    cfg = cs.parse_config(cs.SAMPLE if hasattr(cs, "SAMPLE") else SAMPLE)
    assert cs.get_current(cfg) == ("gpt-5.6-terra", None)
    assert cs.list_providers(cfg) == {}

def test_default_codex_home(monkeypatch, tmp_path):
    import codex_switch as cs
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    assert cs.default_codex_home() == str(tmp_path)
    monkeypatch.delenv("CODEX_HOME")
    assert cs.default_codex_home().endswith(".codex")
```

（`SAMPLE` 最终放测试文件顶部，不进 codex_switch.py；上面 `hasattr` 判断仅为示例，实现时直接用测试文件里的常量。）

- [ ] **Step 3: Run 测试确认失败**

Run: `python -m pytest codex-switch/tests -v`
Expected: FAIL（`No module named codex_switch` 或 AttributeError）

- [ ] **Step 4: 实现**

`codex-switch/codex_switch.py`：模块 docstring（用法同 model_switch.py 风格，列出四命令与 `--codex-home`）；imports；上述六个函数。`mask` 直接照搬 model_switch.py:65-71。

- [ ] **Step 5: Run 测试确认通过**

Run: `python -m pytest codex-switch/tests -v`
Expected: PASS

- [ ] **Step 6: 提交命令（打印给用户，不执行）**

```bash
git add codex-switch/ && git commit -m "codex-switch：脚手架与 config.toml 读取解析

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: TOML 文本编辑纯函数

**Files:**
- Modify: `codex-switch/codex_switch.py`
- Modify: `codex-switch/tests/test_codex_switch.py`

**Interfaces:**
- Consumes: `parse_config`（Task 1）
- Produces:
  - `toml_quote(s: str) -> str`（= `json.dumps(s, ensure_ascii=False)`）
  - `set_current_provider(text: str, provider_key: str | None, model: str | None = None) -> str`
  - `upsert_provider_section(text: str, key: str, fields: dict[str, str]) -> str`

`set_current_provider` 算法（唯一允许的实现方式）：
- 顶层区域 = 第一个以 `[` 开头的行之前的所有行；逐行处理，其余行原样保留。
- `model_provider` 行匹配 `^\s*model_provider\s*=`：`provider_key` 为 None → 整行删除；否则整行替换为 `model_provider = <toml_quote(provider_key)>`。
- 未找到且 `provider_key` 非 None → 插入：有顶层 `model` 行（`^\s*model\s*=`）则插其行后，否则插文件第一行。
- `model` 非 None → 顶层 `model` 行替换为 `model = <toml_quote(model)>`；无该行则插到文件最顶（在 model_provider 之前）。`model_reasoning_effort` 不得被匹配。

`upsert_provider_section` 算法：
- key 校验由调用方负责，本函数假定 `key` 匹配 `^[A-Za-z0-9_-]+$`。
- 渲染块：`[model_providers.<key>]` 头 + fields 中存在的字段按 `name → base_url → env_key → wire_api` 顺序各占一行 `<字段> = <toml_quote(值)>`。
- 已有同名段（header 匹配 `^\[model_providers\.<key>\]\s*$`）：替换段头至下一个 `^\[` header（或 EOF）之间的内容，段头前内容与段后空行原样保留；若段尾紧贴下一 header 则渲染块后补一空行。
- 无同名段：追加到文件末尾，文件非空且末尾无空行时先补一个空行。

- [ ] **Step 1: 写失败测试**

```python
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
        "name": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "env_key": "GLM_API_KEY", "wire_api": "chat"})
    cfg = cs.parse_config(t)
    assert cfg["model_providers"]["glm"]["env_key"] == "GLM_API_KEY"
    assert "[projects.'d:\\work\\iptv\\src']" in t
    t2 = cs.upsert_provider_section(t, "glm", {"name": "x", "base_url": "https://a.b/c",
                                               "env_key": "GLM_API_KEY", "wire_api": "responses"})
    assert cs.parse_config(t2)["model_providers"]["glm"]["wire_api"] == "responses"
    assert t2.count("[model_providers.glm]") == 1
```

- [ ] **Step 2: Run 确认失败**

Run: `python -m pytest codex-switch/tests -v`
Expected: 新增 3 条 FAIL（AttributeError）

- [ ] **Step 3: 按上述算法实现三个函数**

- [ ] **Step 4: Run 确认通过**

Run: `python -m pytest codex-switch/tests -v`
Expected: PASS

- [ ] **Step 5: 提交命令（打印给用户，不执行）**

```bash
git add codex-switch/ && git commit -m "codex-switch：config.toml 文本精准编辑纯函数

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: 备份、env 快照与安全写入

**Files:**
- Modify: `codex-switch/codex_switch.py`
- Modify: `codex-switch/tests/test_codex_switch.py`

**Interfaces:**
- Consumes: `parse_config`、`list_providers`（Task 1）
- Produces:
  - `env_var_value(name: str, reader=None) -> str | None`：`reader` 为 `Callable[[str], str | None]`；缺省实现先 `winreg` 读 `HKCU\Environment`，异常/非 Windows 回落 `os.environ.get`
  - `snapshot_env_vars(cfg: dict, reader=None) -> dict[str, str]`：收集所有 provider 的 `env_key`，值取 `env_var_value`，为 None 的键跳过
  - `backup_before_write(codex_home: str, cfg: dict, reader=None) -> str`：无 `backup-*` 目录 → 创建 `backup-<YYYYMMDD-HHMMSS>/`，复制 config.toml 与 auth.json（存在才复制），写入 `env-snapshot.json`（JSON，ensure_ascii=False），返回该目录；已有 → 复制 config.toml 为 `dirs[0]/config.toml.bak-<YYYYMMDD-HHMMSS>`（tempfile+replace），返回该目录
  - `atomic_write_text(path: str, text: str) -> None`（tempfile + `os.replace`，模板同 model_switch.py:153-169）
  - `modify_config(path: str, new_text: str, codex_home: str, reader=None) -> str`：顺序固定为 ① `backup_before_write` ② `tomllib.loads(new_text)` 校验（失败→`err`+exit(1)，不落盘）③ `atomic_write_text`；返回备份目录

- [ ] **Step 1: 写失败测试**

```python
def test_backup_first_run_and_subsequent(tmp_path):
    import codex_switch as cs, json, os
    home = tmp_path; (home / "config.toml").write_text(SAMPLE, encoding="utf-8")
    (home / "auth.json").write_text("{}", encoding="utf-8")
    cfg = cs.parse_config(SAMPLE)
    d1 = cs.backup_before_write(str(home), cfg, reader=lambda n: None)
    assert (d1 / ".." ).resolve() == home.resolve()
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
```

- [ ] **Step 2: Run 确认失败**

Run: `python -m pytest codex-switch/tests -v`
Expected: 新增 2 条 FAIL（AttributeError）

- [ ] **Step 3: 实现**（`winreg` 导入放 try/except，非 Windows 置 None）

- [ ] **Step 4: Run 确认通过**

Run: `python -m pytest codex-switch/tests -v`
Expected: PASS

- [ ] **Step 5: 提交命令（打印给用户，不执行）**

```bash
git add codex-switch/ && git commit -m "codex-switch：首次全量快照、增量备份与原子写入校验

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: switch 命令

**Files:**
- Modify: `codex-switch/codex_switch.py`
- Modify: `codex-switch/tests/test_codex_switch.py`

**Interfaces:**
- Consumes: `set_current_provider`（Task 2）、`modify_config`（Task 3）、`load_config_text`/`parse_config`/`list_providers`/`env_var_value`（Task 1/3）
- Produces: `cmd_switch(args) -> int`；`main() -> None`（argparse：`command` 默认 `list`，`key`，`--model`，`--codex-home`，UTF-8 reconfigure 同 model_switch.py:285-291）。约定：`switch official` = 切回 OpenAI 官方（删除 `model_provider` 行）

- [ ] **Step 1: 写失败测试**

```python
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
    assert "重启" in capsys.readouterr().out  # Review Focus 5

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
```

- [ ] **Step 2: Run 确认失败**

Run: `python -m pytest codex-switch/tests -v`
Expected: 新增 3 条 FAIL

- [ ] **Step 3: 实现 cmd_switch 与 main()**（switch 不存在的 key → `err`+exit(1)；official 走 `set_current_provider(text, None, model)`；输出含 name/base_url/wire_api/env_key 变量有无（只报有无）、备份目录、重启提示）

- [ ] **Step 4: Run 确认通过**

Run: `python -m pytest codex-switch/tests -v`
Expected: PASS

- [ ] **Step 5: 提交命令（打印给用户，不执行）**

```bash
git add codex-switch/ && git commit -m "codex-switch：switch 命令（含切回 OpenAI 官方）

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: add 命令

**Files:**
- Modify: `codex-switch/codex_switch.py`
- Modify: `codex-switch/tests/test_codex_switch.py`

**Interfaces:**
- Consumes: `upsert_provider_section`（Task 2）、`modify_config`（Task 3）、`env_var_value`（Task 3）
- Produces:
  - `cmd_add(args, setter=None, reader=None) -> int`（`setter`/`reader` 可注入供测试）；args 字段：`key, name, base_url, env_key, wire_api, set_env_var, force, force_env, codex_home`
  - `set_env_var_persist(name: str, value: str, setter=None) -> None`：`setter` 可注入；缺省 Windows 下 `subprocess.run(["setx", name, value], check=True, capture_output=True)`，非 Windows → `err`+exit(1)（提示手动 export）

`cmd_add` 校验顺序（全部通过才动配置）：key 匹配 `^[A-Za-z0-9_-]+$`；重复且无 `--force` → exit(1)；`name`/`base-url`/`env-key` 必填；`base-url` 以 `http://`/`https://` 开头；`env-key` 匹配 `^[A-Za-z_][A-Za-z0-9_]*$`；`wire_api` ∈ {chat, responses}（缺省 `chat`）；`--set-env-var` 给出且 `env_var_value(name)` 非 None 且无 `--force-env` → exit(1)（不静默覆盖）。执行顺序：先 `modify_config` 写入小节，再 `--set-env-var` 设变量。

- [ ] **Step 1: 写失败测试**

```python
def test_add_cmd_appends_section_and_sets_var(tmp_path, capsys):
    import codex_switch as cs
    home = tmp_path; (home / "config.toml").write_text(SAMPLE, encoding="utf-8")
    setter_calls = []
    rc = cs.cmd_add(type("A", (), {"key": "glm", "name": "智谱", "base_url": "https://a.b/c",
        "env_key": "GLM_API_KEY", "wire_api": None, "set_env_var": "sk-test123",
        "force": False, "force_env": False, "codex_home": str(home),
        })(), setter=lambda n, v: setter_calls.append((n, v)))
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
```

- [ ] **Step 2: Run 确认失败**

Run: `python -m pytest codex-switch/tests -v`
Expected: 新增 2 条 FAIL

- [ ] **Step 3: 实现 cmd_add（`reader`/`setter` 作可选 kwargs 注入）与 argparse flags**（`--name --base-url --env-key --wire-api --set-env-var --force --force-env`）

- [ ] **Step 4: Run 确认通过**

Run: `python -m pytest codex-switch/tests -v`
Expected: PASS

- [ ] **Step 5: 提交命令（打印给用户，不执行）**

```bash
git add codex-switch/ && git commit -m "codex-switch：add 命令（录入提供商与代设环境变量）

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: list/status、README 与冒烟

**Files:**
- Modify: `codex-switch/codex_switch.py`
- Create: `codex-switch/README.md`
- Modify: `codex-switch/tests/test_codex_switch.py`

**Interfaces:**
- Consumes: Task 1-5 全部
- Produces: `cmd_list(args) -> int`、`cmd_status(args) -> int`；README 用法文档

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: Run 确认失败** → **Step 3: 实现**（list：无 provider 时提示 add 用法；逐条含序号/key/name/base_url/env_key 变量已设或未设/wire_api/当前生效标记；status：model、model_provider（无→"OpenAI 官方（ChatGPT 登录）"）、匹配详情）→ **Step 4: Run 确认通过**

- [ ] **Step 5: README.md**

内容：定位（零模型依赖、独立 CLI、不做 skill/插件的理由一句话）、安装（clone 仓库直接 `python codex-switch/codex_switch.py`）、四命令用法与示例、`--codex-home`/`CODEX_HOME`、备份与 env-snapshot 位置及"含明文 key 勿外传"警告、切换后需完全重启 Codex 的说明。

- [ ] **Step 6: 冒烟（沙盒副本 + 真实只读）**

Run:
```bash
python codex-switch/codex_switch.py list --codex-home "$TEMP/codex-switch-smoke"
python codex-switch/codex_switch.py status
```
Expected: 沙盒目录为空时 list 提示 add 用法不报错；status 对真实 `~/.codex` 只读显示 `OpenAI 官方（ChatGPT 登录）`、model=gpt-5.6-terra。**不**对真实 config.toml 执行 switch/add。

- [ ] **Step 7: 提交命令（打印给用户，不执行）**

```bash
git add codex-switch/ && git commit -m "codex-switch：list/status 命令与 README

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

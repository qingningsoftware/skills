#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""codex-switch: 切换 OpenAI Codex 的模型提供商配置（零模型依赖）。

本脚本可独立运行；也可经 model_switch.py 的 codex 子命令调用（`model_switch.py codex list` 等价于 `codex_switch.py list`）。

用法:
  python codex_switch.py list               # 列出 config.toml 中的提供商，标记当前生效
  python codex_switch.py status             # 查看当前 model / model_provider
  python codex_switch.py switch <key>       # 切换到指定提供商（自动备份 config.toml）
  python codex_switch.py switch official    # 切回 OpenAI 官方（ChatGPT 登录，删除 model_provider 行）
  python codex_switch.py add <key> ...      # 添加提供商（可选代设环境变量）

选项:
  --codex-home <path>   指定 .codex 目录（默认 CODEX_HOME 环境变量，否则 ~/.codex）
  --model <id>          switch: 同时改写顶部 model 行（可选）

说明:
  - 提供商定义在 config.toml 的 [model_providers.<key>] 小节；切换只改顶部
    model / model_provider 两行，永不碰环境变量。
  - key 本体存系统环境变量（env_key 只写变量名），每家一个独立变量名，设一次常驻。
  - 任何修改前先备份：首次运行全量快照到 ~/.codex/backup-<时间戳>/，
    此后每次修改前向同一目录追加 config.toml.bak-<时间戳> 副本。
  - 切换后需完全退出（含托盘）并重启 Codex 才生效（Codex 启动时读配置）。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from datetime import datetime
from pathlib import Path

try:
    import winreg
except ImportError:  # 非 Windows
    winreg = None

CODEX_HOME_ENV = "CODEX_HOME"
SECTION_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def default_codex_home() -> str:
    """Codex 配置目录：优先 CODEX_HOME，否则 ~/.codex。"""
    d = os.environ.get(CODEX_HOME_ENV)
    return d if d else os.path.join(os.path.expanduser("~"), ".codex")


def out(*args):
    print(*args, flush=True)


def err(*args):
    print(*args, file=sys.stderr, flush=True)


def mask(token: str) -> str:
    """token 脱敏：保留头尾少量字符，防止截图/分享时泄露。"""
    if not token:
        return "(空)"
    if len(token) <= 10:
        return token[:2] + "****"
    return token[:5] + "****" + token[-4:]


def load_config_text(path: str) -> str:
    """读取 config.toml 文本；文件不存在返回空串。"""
    if not os.path.isfile(path):
        return ""
    # utf-8-sig：兼容记事本"UTF-8 with BOM"保存的配置；写回为无 BOM 纯 UTF-8
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def parse_config(text: str) -> dict:
    """tomllib 解析（只读用途）；空串视为空配置，解析失败直接退出。"""
    if not text.strip():
        return {}
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        err(f"错误: 解析 config.toml 失败:\n  {e}")
        sys.exit(1)


def get_current(cfg: dict) -> tuple:
    """当前顶层选择：(model, model_provider)，均可能为 None。"""
    return cfg.get("model"), cfg.get("model_provider")


def list_providers(cfg: dict) -> dict:
    """全部提供商定义：key -> {name, base_url, env_key, wire_api}。"""
    return cfg.get("model_providers", {}) or {}


# ---------- TOML 文本精准编辑（纯函数） ----------

FIELD_ORDER = ("name", "base_url", "env_key", "wire_api")


def toml_quote(s: str) -> str:
    """TOML 基本字符串字面量（json.dumps 的转义与 TOML 基本字符串兼容）。"""
    return json.dumps(s, ensure_ascii=False)


def set_current_provider(text: str, provider_key, model=None) -> str:
    """只改顶层 model / model_provider 两行，其余内容（含注释与小节）逐行保留。

    provider_key=None 表示切回 OpenAI 官方：删除 model_provider 行。
    model 非 None 时同步改写顶层 model 行（无则插到文件最顶）。
    """
    lines = text.split("\n")

    def top_bounds(ls):
        section_start = next((i for i, l in enumerate(ls) if l.startswith("[")), len(ls))
        return section_start

    # 第一遍：model_provider 行（替换 / 删除 / 插入）
    section_start = top_bounds(lines)
    prov_idx = next(
        (i for i in range(section_start) if re.match(r"^\s*model_provider\s*=", lines[i])),
        None,
    )
    if provider_key is None:
        if prov_idx is not None:
            del lines[prov_idx]
    elif prov_idx is not None:
        lines[prov_idx] = f"model_provider = {toml_quote(provider_key)}"
    else:
        section_start = top_bounds(lines)
        model_idx = next(
            (i for i in range(section_start) if re.match(r"^\s*model\s*=", lines[i])),
            None,
        )
        new_line = f"model_provider = {toml_quote(provider_key)}"
        if model_idx is not None:
            lines.insert(model_idx + 1, new_line)
        else:
            lines.insert(0, new_line)

    # 第二遍：model 行（替换 / 插到最顶，位于 model_provider 之前）
    if model is not None:
        section_start = top_bounds(lines)
        model_idx = next(
            (i for i in range(section_start) if re.match(r"^\s*model\s*=", lines[i])),
            None,
        )
        new_line = f"model = {toml_quote(model)}"
        if model_idx is not None:
            lines[model_idx] = new_line
        else:
            lines.insert(0, new_line)

    return "\n".join(lines)


def render_provider_section(key: str, fields: dict) -> str:
    lines = [f"[model_providers.{key}]"]
    for f in FIELD_ORDER:
        if f in fields:
            lines.append(f"{f} = {toml_quote(fields[f])}")
    return "\n".join(lines) + "\n"


def upsert_provider_section(text: str, key: str, fields: dict) -> str:
    """插入或替换 [model_providers.<key>] 小节，其余内容逐行保留。"""
    header_re = re.compile(rf"^\[model_providers\.{re.escape(key)}\]\s*$")
    lines = text.split("\n")
    header_idx = next((i for i, l in enumerate(lines) if header_re.match(l)), None)
    if header_idx is None:
        new_text = text
        if new_text and not new_text.endswith("\n\n"):
            if not new_text.endswith("\n"):
                new_text += "\n"
            new_text += "\n"
        return new_text + render_provider_section(key, fields)
    end_idx = next(
        (i for i in range(header_idx + 1, len(lines)) if lines[i].startswith("[")),
        len(lines),
    )
    block_lines = render_provider_section(key, fields).rstrip("\n").split("\n")
    after = lines[end_idx:]
    if after and after[0].startswith("["):
        block_lines.append("")  # 原段尾紧贴下一 header，补一个空行
    return "\n".join(lines[:header_idx] + block_lines + after)


# ---------- 环境变量读取、备份与安全写入 ----------

def env_var_value(name: str, reader=None):
    """环境变量当前值：优先注册表 HKCU\\Environment 真值（setx 后进程环境可能过期）。"""
    if reader is not None:
        return reader(name)
    if winreg is not None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                val, _ = winreg.QueryValueEx(k, name)
                return val if isinstance(val, str) else None
        except OSError:
            pass
    return os.environ.get(name)


def snapshot_env_vars(cfg: dict, reader=None) -> dict:
    """收集所有 provider 的 env_key -> 当前值；取不到值的键跳过。"""
    result = {}
    for p in list_providers(cfg).values():
        name = p.get("env_key")
        if not name:
            continue
        val = env_var_value(name, reader)
        if val is not None:
            result[name] = val
    return result


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def backup_before_write(codex_home: str, cfg: dict, reader=None) -> Path:
    """修改前备份：首次运行全量快照（config.toml/auth.json/env-snapshot.json），
    此后向首个 backup-* 目录追加 config.toml.bak-<时间戳> 副本。返回备份目录。"""
    home = Path(codex_home)
    existing = sorted(home.glob("backup-*"))
    src = home / "config.toml"
    if existing:
        target_dir = existing[0]
        if src.is_file():
            fd, tmp = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
            os.close(fd)
            shutil.copy2(src, tmp)
            os.replace(tmp, target_dir / f"config.toml.bak-{_stamp()}")
        return target_dir
    target_dir = home / f"backup-{_stamp()}"
    target_dir.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        shutil.copy2(src, target_dir / "config.toml")
    auth = home / "auth.json"
    if auth.is_file():
        shutil.copy2(auth, target_dir / "auth.json")
    snapshot = snapshot_env_vars(cfg, reader)
    atomic_write_text(
        str(target_dir / "env-snapshot.json"),
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
    )
    return target_dir


def atomic_write_text(path: str, text: str) -> None:
    """原子写入文本：先写临时文件，再替换，避免写一半损坏文件。"""
    target_dir = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp_path = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp_path, path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    except OSError as e:
        err(f"错误: 原子写入失败: {path}\n  {e}")
        sys.exit(1)


def modify_config(path: str, new_text: str, codex_home: str, reader=None) -> str:
    """修改 config.toml 的唯一入口：先备份 → tomllib 校验新文本（失败不落盘）→ 原子写入。"""
    old_cfg = parse_config(load_config_text(path))
    backup_dir = backup_before_write(codex_home, old_cfg, reader)
    try:
        tomllib.loads(new_text)
    except tomllib.TOMLDecodeError as e:
        err(f"错误: 新配置不是合法 TOML，已放弃写入（备份仍在: {backup_dir}）:\n  {e}")
        sys.exit(1)
    atomic_write_text(path, new_text)
    return str(backup_dir)


# ---------- 命令 ----------

def config_file(codex_home: str) -> str:
    return os.path.join(codex_home, "config.toml")


OFFICIAL_KEY = "official"


def cmd_switch(args) -> int:
    codex_home = args.codex_home
    path = config_file(codex_home)
    key = args.key

    provider = None
    if key != OFFICIAL_KEY:
        providers = list_providers(parse_config(load_config_text(path)))
        if key not in providers:
            err(f"错误: 没有名为 '{key}' 的提供商。可用: {', '.join(providers) or '(无，请先用 add 添加)'}")
            err("切回 OpenAI 官方请用: switch official")
            sys.exit(1)
        provider = providers[key]

    text = load_config_text(path)
    provider_key = None if key == OFFICIAL_KEY else key
    new_text = set_current_provider(text, provider_key, getattr(args, "model", None))
    backup_dir = modify_config(path, new_text, codex_home)

    if key == OFFICIAL_KEY:
        out("已切回 OpenAI 官方（ChatGPT 登录，无需 API key）")
    else:
        env_name = provider.get("env_key", "")
        state = "已设置" if env_var_value(env_name) is not None else "未设置（请先 setx 设置）"
        out(f"当前模型已修改成 {provider.get('name', key)}（{key}）")
        out(f"  baseUrl: {provider.get('base_url', '')}")
        out(f"  wire_api: {provider.get('wire_api', '')}")
        if getattr(args, "model", None):
            out(f"  model: {args.model}")
        out(f"  环境变量 {env_name}: {state}")
    out(f"  备份: {backup_dir}")
    out("请完全退出（含托盘）并重启 Codex 后生效。")
    return 0


def set_env_var_persist(name: str, value: str, setter=None) -> None:
    """把 key 写入用户环境变量（setx，注册表真值，新进程生效）。"""
    if setter is not None:
        setter(name, value)
        return
    if os.name == "nt":
        subprocess.run(["setx", name, value], check=True, capture_output=True)
        return
    err(f"错误: 当前系统不支持 setx，请手动设置环境变量后再试: export {name}=<值>")
    sys.exit(1)


def cmd_add(args, setter=None, reader=None) -> int:
    codex_home = args.codex_home
    path = config_file(codex_home)
    key = args.key
    if not key or not SECTION_KEY_RE.match(key):
        err("错误: add 需要合法提供商 key（字母/数字/下划线/连字符）。")
        err("用法: python codex_switch.py add <key> --name <名称> --base-url <url> --env-key <变量名>")
        sys.exit(1)
    if key == OFFICIAL_KEY:
        err("错误: 'official' 是保留 key（switch official = 切回 OpenAI 官方），不能用作提供商 key。")
        sys.exit(1)

    providers = list_providers(parse_config(load_config_text(path)))
    if key in providers and not args.force:
        err(f"错误: 已存在名为 '{key}' 的提供商（{providers[key].get('name', key)}）。")
        err(f"如需覆盖请加 --force。可用 key: {', '.join(providers)}")
        sys.exit(1)

    missing = [f for f in ("name", "base_url", "env_key") if not getattr(args, f)]
    if missing:
        err(f"错误: 缺少必填参数: {', '.join('--' + m.replace('_', '-') for m in missing)}")
        sys.exit(1)
    base_url = args.base_url
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        err(f"错误: base-url 必须以 http:// 或 https:// 开头，收到: {base_url}")
        sys.exit(1)
    env_key = args.env_key
    if not ENV_KEY_RE.match(env_key):
        err(f"错误: env-key 不是合法环境变量名: {env_key}")
        sys.exit(1)
    wire_api = args.wire_api or "chat"
    if wire_api not in ("chat", "responses"):
        err(f"错误: wire-api 只能是 chat 或 responses，收到: {wire_api}")
        sys.exit(1)

    # 已有变量不静默覆盖
    set_env = getattr(args, "set_env_var", None)
    if set_env is not None and env_var_value(env_key, reader) is not None and not args.force_env:
        err(f"错误: 环境变量 {env_key} 已存在，如需覆盖请加 --force-env。")
        sys.exit(1)

    text = load_config_text(path)
    new_text = upsert_provider_section(text, key, {
        "name": args.name, "base_url": base_url, "env_key": env_key, "wire_api": wire_api,
    })
    backup_dir = modify_config(path, new_text, codex_home)

    out(f"已{'覆盖' if key in providers else '添加'}提供商: {args.name}（{key}）")
    out(f"  baseUrl: {base_url}")
    out(f"  env_key: {env_key}")
    out(f"  wire_api: {wire_api}")
    out(f"  备份: {backup_dir}")
    if set_env is not None:
        set_env_var_persist(env_key, set_env, setter)
        out(f"  环境变量 {env_key} 已写入（对新启动的进程生效）")
    out(f"切换到它: python codex_switch.py switch {key}")
    return 0


def cmd_list(args) -> int:
    codex_home = args.codex_home
    path = config_file(codex_home)
    cfg = parse_config(load_config_text(path))
    providers = list_providers(cfg)
    model, provider_key = get_current(cfg)
    out(f"配置文件: {path}")
    out(f"当前 model: {model or '(未设置)'}")
    out(f"当前 model_provider: {provider_key or '(无 —— OpenAI 官方，ChatGPT 登录)'}")
    out("")
    if not providers:
        out("尚未定义任何提供商。添加示例:")
        out("  python codex_switch.py add <key> --name <名称> --base-url <提供商的OpenAI兼容地址> --env-key <变量名>")
        return 0
    out(f"可用提供商（共 {len(providers)} 个）:")
    for i, (key, p) in enumerate(providers.items(), 1):
        mark = "  <-- 当前生效" if key == provider_key else ""
        out(f"{i:>2}. {key:<12} {p.get('name', key)}{mark}")
        out(f"     baseUrl: {p.get('base_url', '(未配置)')}")
        env_name = p.get("env_key", "")
        state = "已设置" if env_var_value(env_name) is not None else "未设置"
        out(f"     env_key: {env_name}（{state}）")
        out(f"     wire_api: {p.get('wire_api', '')}")
    out("")
    out("切换: python codex_switch.py switch <key>（切回官方: switch official）")
    return 0


def cmd_status(args) -> int:
    codex_home = args.codex_home
    path = config_file(codex_home)
    cfg = parse_config(load_config_text(path))
    providers = list_providers(cfg)
    model, provider_key = get_current(cfg)
    out(f"当前配置（{path}）:")
    out(f"  model: {model or '(未设置)'}")
    if provider_key is None:
        out("  model_provider: 无 —— OpenAI 官方（ChatGPT 登录）")
    elif provider_key in providers:
        p = providers[provider_key]
        out(f"  model_provider: {provider_key}（{p.get('name', provider_key)}）")
        out(f"    baseUrl: {p.get('base_url', '')}")
        env_name = p.get("env_key", "")
        state = "已设置" if env_var_value(env_name) is not None else "未设置"
        out(f"    env_key: {env_name}（{state}）")
        out(f"    wire_api: {p.get('wire_api', '')}")
    else:
        out(f"  model_provider: {provider_key}（config.toml 中无对应定义，可能是自定义配置）")
    return 0


def main():
    # Windows 下被管道捕获时默认是 ANSI 代码页（GBK），强制 UTF-8 输出避免乱码。
    try:
        if not sys.stdout.isatty():
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if not sys.stderr.isatty():
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        prog="codex_switch.py", description="切换 Codex 模型提供商（零模型依赖）"
    )
    parser.add_argument(
        "command", nargs="?", default="list",
        choices=["list", "status", "switch", "add"],
        help="list=列出提供商; status=查看当前配置; switch=切换; add=添加提供商（不带命令时等同 list）",
    )
    parser.add_argument("key", nargs="?", help="switch/add 的提供商 key（switch official=切回 OpenAI 官方）")
    parser.add_argument("--model", help="switch: 同时改写顶部 model 行（可选）")
    parser.add_argument("--name", help="add: 提供商显示名称（必填）")
    parser.add_argument("--base-url", help="add: OpenAI 兼容 base URL，http(s):// 开头（必填）")
    parser.add_argument("--env-key", help="add: 存放 key 的环境变量名（必填）")
    parser.add_argument("--wire-api", choices=["chat", "responses"], default=None,
                        help="add: 协议类型（默认 chat）")
    parser.add_argument("--set-env-var", metavar="VALUE", help="add: 代设环境变量为该值（可选）")
    parser.add_argument("--force", action="store_true", help="add: 覆盖同名提供商")
    parser.add_argument("--force-env", action="store_true", help="add: 允许覆盖已存在的环境变量")
    parser.add_argument("--codex-home", default=default_codex_home(),
                        help="指定 .codex 目录（默认 CODEX_HOME 环境变量，否则 ~/.codex）")
    args = parser.parse_args()

    if args.command == "add":
        sys.exit(cmd_add(args))
    if args.command == "switch":
        if not args.key:
            err("错误: switch 需要提供商 key。用法: python codex_switch.py switch <key|official>")
            err("可用提供商请运行: python codex_switch.py list")
            sys.exit(1)
        sys.exit(cmd_switch(args))
    if args.command == "status":
        sys.exit(cmd_status(args))
    sys.exit(cmd_list(args))


if __name__ == "__main__":
    main()

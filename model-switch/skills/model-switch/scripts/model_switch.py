#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""model-switch: 切换 Claude Code 的模型提供商配置。

用法:
  python model_switch.py list              # 列出所有提供商，标记当前生效
  python model_switch.py status            # 查看 settings.json 当前生效配置
  python model_switch.py switch <key>      # 切换到指定提供商（自动备份 settings.json）
  python model_switch.py add <key> ...     # 添加提供商（自动备份 model-profiles.json）
                                           # 必填: --name --base-url --token
                                           # 可选: --opus --sonnet --haiku --force(覆盖同名)

Codex 宿主（零模型切 ~/.codex/config.toml，同一脚本 codex 子命令）:
  python model_switch.py codex list|status|switch|add ...
  # 等价于 codex_switch.py 的同名命令；switch official = 切回 OpenAI 官方

选项:
  --profiles <path>   指定 model-profiles.json 路径（默认 <配置目录>/model-profiles.json）
  --settings <path>   指定 settings.json 路径（默认 <配置目录>/settings.json）

配置目录: 设置了 CLAUDE_CONFIG_DIR 环境变量时用该目录，否则为 ~/.claude。

说明:
  - model-profiles.json 是唯一配置源；脚本只改写 settings.json 的 env 中这 5 个变量:
      ANTHROPIC_BASE_URL
      ANTHROPIC_AUTH_TOKEN
      ANTHROPIC_DEFAULT_OPUS_MODEL
      ANTHROPIC_DEFAULT_SONNET_MODEL
      ANTHROPIC_DEFAULT_HAIKU_MODEL
  - 其余变量（包括带 -glm/-qwen 等后缀的备份变量）一律原样保留。
  - profile 里缺失的 model 档位对应的 DEFAULT_*_MODEL 变量会被移除（交由该平台默认模型）。
  - 每次切换前把 settings.json 备份到 settings.json.bak-model-switch，写入采用临时文件+原子替换。
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

PROFILE_FIELDS = ("opus", "sonnet", "haiku")
MODEL_VARS = {
    "opus": "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "sonnet": "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "haiku": "ANTHROPIC_DEFAULT_HAIKU_MODEL",
}
BASE_URL_VAR = "ANTHROPIC_BASE_URL"
TOKEN_VAR = "ANTHROPIC_AUTH_TOKEN"
BACKUP_NAME = "settings.json.bak-model-switch"
OFFICIAL_KEY = "official"
# switch official 时从 settings.json env 移除的变量（切回 Claude Code 官方登录）
MANAGED_VARS = (BASE_URL_VAR, TOKEN_VAR) + tuple(MODEL_VARS.values())
PROFILES_BACKUP_NAME = "model-profiles.json.bak"
CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"


def default_config_dir() -> str:
    """Claude Code 用户级配置目录：优先 CLAUDE_CONFIG_DIR，否则 ~/.claude。"""
    d = os.environ.get(CONFIG_DIR_ENV)
    return d if d else os.path.join(os.path.expanduser("~"), ".claude")


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


def load_json(path: str, what: str):
    if not os.path.isfile(path):
        err(f"错误: 找不到{what}: {path}")
        sys.exit(1)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        err(f"错误: 读取{what}失败: {path}\n  {e}")
        sys.exit(1)


def model_summary(profile: dict) -> str:
    m = profile.get("model") or {}
    if not m:
        return "(无 model 映射，使用平台默认)"
    return " | ".join(
        f"{tier}={m[tier]}" for tier in PROFILE_FIELDS if m.get(tier)
    ) or "(无 model 映射，使用平台默认)"


def find_active_key(settings: dict, profiles: dict):
    """按 baseUrl+token(+models) 匹配当前生效的 profile；匹配不到返回 None。"""
    env = settings.get("env", {})
    base_url = env.get(BASE_URL_VAR)
    token = env.get(TOKEN_VAR)
    if not base_url or not token:
        return None
    candidates = [
        k for k, p in profiles.items()
        if p.get("baseUrl") == base_url and p.get("token") == token
    ]
    if len(candidates) <= 1:
        return candidates[0] if candidates else None
    # 多个候选（如 openrouter/ox 共用同一路由）时，进一步比对三档模型
    tier_vals = tuple(env.get(MODEL_VARS[t], "") for t in PROFILE_FIELDS)
    exact = [
        k for k in candidates
        if tuple((profiles[k].get("model") or {}).get(t, "") for t in PROFILE_FIELDS) == tier_vals
    ]
    if len(exact) == 1:
        return exact[0]
    return None


def cmd_list(args):
    profiles = load_json(args.profiles, "model-profiles.json")
    settings = load_json(args.settings, "settings.json")
    active = find_active_key(settings, profiles)
    out(f"可用模型提供商（共 {len(profiles)} 个，来源: {args.profiles}）:")
    out("")
    for i, (key, p) in enumerate(profiles.items(), 1):
        mark = "  <-- 当前生效" if key == active else ""
        out(f"{i:>2}. {key:<12} {p.get('name', key)}{mark}")
        out(f"     baseUrl: {p.get('baseUrl', '(未配置)')}")
        out(f"     token:   {mask(p.get('token', ''))}")
        out(f"     models:  {model_summary(p)}")
    out("")
    out("切换: python model_switch.py switch <key>")
    return 0


def cmd_status(args):
    profiles = load_json(args.profiles, "model-profiles.json")
    settings = load_json(args.settings, "settings.json")
    env = settings.get("env", {})
    out(f"当前生效配置（{args.settings} 的 env）:")
    out(f"  {BASE_URL_VAR}: {env.get(BASE_URL_VAR, '(未设置)')}")
    out(f"  {TOKEN_VAR}: {mask(env.get(TOKEN_VAR, ''))}")
    for tier in PROFILE_FIELDS:
        out(f"  {MODEL_VARS[tier]}: {env.get(MODEL_VARS[tier], '(未设置)')}")
    active = find_active_key(settings, profiles)
    if active:
        out(f"匹配提供商: {active} ({profiles[active].get('name', active)})")
    else:
        out("匹配提供商: 无（当前配置不来自 model-profiles.json，或为自定义配置）")
    return 0


def atomic_write_json(path: str, data):
    """原子写入 JSON：先写临时文件，再替换，避免写一半损坏文件。"""
    target_dir = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp_path = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp_path, path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    except OSError as e:
        err(f"错误: 原子写入失败: {path}\n  {e}")
        sys.exit(1)


def load_profiles_or_empty(path: str) -> dict:
    """读取 model-profiles.json；不存在则返回空 dict（首次 add 自动创建）。"""
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        err(f"错误: 读取 model-profiles.json 失败: {path}\n  {e}")
        sys.exit(1)
    if not isinstance(data, dict):
        err(f"错误: {path} 的顶层应为对象（key -> profile）")
        sys.exit(1)
    return data


def cmd_add(args):
    key = args.key
    if not key:
        err("错误: add 需要提供商 key。用法: python model_switch.py add <key> --name <名称> --base-url <url> --token <token>")
        sys.exit(1)
    if key == OFFICIAL_KEY:
        err("错误: 'official' 是保留 key（switch official = 切回 Claude Code 官方登录），不能用作提供商 key。")
        sys.exit(1)

    profiles = load_profiles_or_empty(args.profiles)
    if key in profiles and not args.force:
        err(f"错误: 已存在名为 '{key}' 的提供商（{profiles[key].get('name', key)}）。")
        err(f"如需覆盖请加 --force。可用 key: {', '.join(profiles)}")
        sys.exit(1)

    # 校验必填项
    missing = [f for f in ("name", "base_url", "token") if not getattr(args, f)]
    if missing:
        err(f"错误: 缺少必填参数: {', '.join('--' + m.replace('_', '-') for m in missing)}")
        sys.exit(1)
    if not (args.base_url.startswith("http://") or args.base_url.startswith("https://")):
        err(f"错误: base-url 必须以 http:// 或 https:// 开头，收到: {args.base_url}")
        sys.exit(1)

    profile = {"name": args.name, "baseUrl": args.base_url, "token": args.token}
    model_map = {t: getattr(args, t) for t in PROFILE_FIELDS if getattr(args, t)}
    if model_map:
        profile["model"] = model_map

    # 写入前备份 model-profiles.json（文件已存在时）
    backup_path = os.path.join(os.path.dirname(os.path.abspath(args.profiles)), PROFILES_BACKUP_NAME)
    if os.path.isfile(args.profiles):
        try:
            shutil.copy2(args.profiles, backup_path)
        except OSError as e:
            err(f"错误: 备份 model-profiles.json 失败: {e}")
            sys.exit(1)

    profiles[key] = profile
    atomic_write_json(args.profiles, profiles)

    action = "已覆盖" if args.force else "已添加"
    out(f"{action}提供商: {args.name}（{key}）")
    out(f"  baseUrl: {args.base_url}")
    out(f"  token:   {mask(args.token)}")
    out(f"  models:  {model_summary(profile)}")
    out(f"  配置文件: {args.profiles}")
    if os.path.isfile(backup_path):
        out(f"  备份:    {backup_path}")
    out(f"切换到它: python model_switch.py switch {key}")
    return 0


def cmd_switch(args):
    key = args.key
    settings = load_json(args.settings, "settings.json")

    if key == OFFICIAL_KEY:
        # 切回官方登录：移除脚本管理的 5 个变量，其余 env 原样保留
        backup_path = os.path.join(os.path.dirname(os.path.abspath(args.settings)), BACKUP_NAME)
        try:
            shutil.copy2(args.settings, backup_path)
        except OSError as e:
            err(f"错误: 备份 settings.json 失败: {e}")
            sys.exit(1)
        env = settings.setdefault("env", {})
        removed = [v for v in MANAGED_VARS if env.pop(v, None) is not None]
        try:
            atomic_write_json(args.settings, settings)
        except SystemExit:
            err(f"备份仍在: {backup_path}")
            raise
        out("已切回 Claude Code 官方登录（默认 Anthropic 配置）")
        out(f"  移除变量: {', '.join(removed) if removed else '（无）'}")
        out(f"  其余 env 变量原样保留；备份: {backup_path}")
        return 0

    profiles = load_json(args.profiles, "model-profiles.json")
    if key not in profiles:
        err(f"错误: 没有名为 '{key}' 的提供商。可用: {', '.join(profiles)}")
        sys.exit(1)
    profile = profiles[key]

    settings = load_json(args.settings, "settings.json")

    # 切换前备份（settings.json.bak-model-switch，每次切换前覆盖为最新快照）
    backup_path = os.path.join(os.path.dirname(os.path.abspath(args.settings)), BACKUP_NAME)
    try:
        shutil.copy2(args.settings, backup_path)
    except OSError as e:
        err(f"错误: 备份 settings.json 失败: {e}")
        sys.exit(1)

    env = settings.setdefault("env", {})
    env[BASE_URL_VAR] = profile.get("baseUrl", "")
    env[TOKEN_VAR] = profile.get("token", "")
    model_map = profile.get("model") or {}
    for tier in PROFILE_FIELDS:
        var = MODEL_VARS[tier]
        if model_map.get(tier):
            env[var] = model_map[tier]
        else:
            env.pop(var, None)  # 缺失档位移除变量，交由平台默认

    # 原子写入：先写临时文件，再替换，避免写一半损坏配置
    try:
        atomic_write_json(args.settings, settings)
    except SystemExit:
        err(f"备份仍在: {backup_path}")
        raise

    out(f"当前模型已修改成 {profile.get('name', key)}（{key}）")
    out(f"  baseUrl: {profile.get('baseUrl', '')}")
    out(f"  models:  {model_summary(profile)}")
    out(f"  备份:    {backup_path}")
    return 0


def main():
    # Windows 下：真实控制台走系统编码即可正常显示中文；
    # 被管道捕获时（如 Claude Code 的 Bash 工具）默认是 ANSI 代码页（GBK），
    # 会与捕获端的 UTF-8 解码不一致导致乱码，因此强制 UTF-8 输出。
    try:
        if not sys.stdout.isatty():
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if not sys.stderr.isatty():
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # 宿主分发：`model_switch.py codex ...` 转发给 Codex 后端（零模型切 ~/.codex/config.toml）；
    # `claude`/缺省 → 本文件原有的 Claude Code 逻辑。
    if len(sys.argv) > 1 and sys.argv[1] in ("codex", "claude"):
        host = sys.argv.pop(1)
        if host == "codex":
            import codex_switch
            codex_switch.main()
            return

    parser = argparse.ArgumentParser(
        prog="model_switch.py", description="切换 Claude Code 模型提供商"
    )
    parser.add_argument(
        "command", nargs="?", default="list",
        choices=["list", "status", "switch", "add"],
        help="list=列出提供商; status=查看当前配置; switch=切换; add=添加提供商（不带命令时等同 list）",
    )
    parser.add_argument("key", nargs="?", help="switch/add 的提供商 key")
    parser.add_argument("--name", help="add: 提供商显示名称（必填）")
    parser.add_argument("--base-url", help="add: API base URL，http(s):// 开头（必填）")
    parser.add_argument("--token", help="add: API token（必填）")
    parser.add_argument("--opus", help="add: opus 档模型映射（可选）")
    parser.add_argument("--sonnet", help="add: sonnet 档模型映射（可选）")
    parser.add_argument("--haiku", help="add: haiku 档模型映射（可选）")
    parser.add_argument("--force", action="store_true", help="add: 覆盖同名提供商")
    parser.add_argument("--profiles", default=os.path.join(default_config_dir(), "model-profiles.json"))
    parser.add_argument("--settings", default=os.path.join(default_config_dir(), "settings.json"))
    args = parser.parse_args()

    if args.command == "add":
        sys.exit(cmd_add(args))
    if args.command == "switch":
        if not args.key:
            err("错误: switch 需要提供商 key。用法: python model_switch.py switch <key>")
            err("可用提供商请运行: python model_switch.py list")
            sys.exit(1)
        sys.exit(cmd_switch(args))
    if args.command == "status":
        sys.exit(cmd_status(args))
    sys.exit(cmd_list(args))


if __name__ == "__main__":
    main()

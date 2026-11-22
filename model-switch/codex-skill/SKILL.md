---
name: codex-switch
description: 切换/查看 OpenAI Codex 的模型提供商（改 ~/.codex/config.toml）。用户想切换 Codex 用的模型或提供商、添加提供商、查看当前 Codex 用哪个模型时使用。
---

# codex-switch

用 Bash 运行本 skill 目录下的脚本（macOS/Linux 把 python 换成 python3）：

- `python <SKILL.md 所在目录>/scripts/model_switch.py codex list` — 列出提供商，标记当前生效
- `python <...>/model_switch.py codex status` — 查看当前 model / model_provider
- `python <...>/model_switch.py codex switch <key>` — 切换（`switch official` = 切回 OpenAI 官方；可加 `--model <id>`）
- `python <...>/model_switch.py codex add <key> --name <名称> --base-url <url> --env-key <变量名> [--set-env-var <token>]` — 添加提供商

注意：切换后提醒用户完全退出（含托盘）并重启 Codex 才生效；token 一律只显示脱敏形式，不要输出完整 token。

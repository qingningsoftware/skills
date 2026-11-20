---
name: model-switch
description: 切换 Claude Code 的模型提供商配置（读写 ~/.claude/model-profiles.json 与 ~/.claude/settings.json）。当用户想切换/更换模型或提供商（如"切换到 glm"、"用 kimi"、"换成千问"、"换回 OpenRouter"、"现在用的什么模型"、"有哪些模型/提供商可用"）、添加新的模型提供商（如"加个提供商"、"添加 kimi 配置"），或输入 /model-switch [list|status|add|<key>] 时，必须使用本 skill。
---

# model-switch — Claude Code 模型提供商切换

配置源是 `~/.claude/model-profiles.json`（每个提供商含 `name`、`baseUrl`、`token`、`model.{opus,sonnet,haiku}`）。切换 = 把选中 profile 的值写入 `~/.claude/settings.json` 的 `env` 中这 5 个变量：`ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_DEFAULT_OPUS_MODEL`、`ANTHROPIC_DEFAULT_SONNET_MODEL`、`ANTHROPIC_DEFAULT_HAIKU_MODEL`。

脚本会自动：每次切换前备份 `settings.json` 到 `settings.json.bak-model-switch`；原子写入；保留其余所有变量（含带 `-glm`/`-qwen` 等后缀的备份变量）不动。

## 脚本位置

本 SKILL.md 同目录下的 `scripts/model_switch.py`（路径相对于本文件解析，个人 skill 与插件两种安装位置均适用）。用 Bash 运行 `python <脚本路径> <命令>`。

## 命令映射

| 用户输入 | 动作 |
|---|---|
| `/model-switch list` | 运行 `python <脚本> list`，把列表展示给用户（token 已脱敏，不要输出完整 token） |
| `/model-switch status` | 运行 `python <脚本> status`，展示当前生效配置 |
| `/model-switch <key>` | 运行 `python <脚本> switch <key>`；成功后告诉用户"当前模型已修改成 <name>（<key>）" |
| `/model-switch`（无参数） | 运行 `list`，把全部提供商整理成 markdown 表格输出（含"当前生效"标记），请用户直接回复要切换的 key。不要用 AskUserQuestion 弹窗做选择——它最多只能显示 4 个选项，提供商多于 4 个时必然列不全 |
| `/model-switch add` | 进入添加模式：先提示用户粘贴以下信息（一次贴齐或分多轮都行，缺哪项追问哪项），收齐后运行脚本写入。**不要把收到的 token 显示在回复里** |

## 添加提供商（/model-switch add）

向用户收集以下信息（提示用户直接粘贴）：

1. **key**：切换命令用的短标识，建议小写英文/数字/连字符（如 `glm`、`kimi`、`my-provider`）
2. **名称**（name）：显示名称（如 `GLM`、`Kimi`）
3. **baseUrl**：API 地址，必须 `http://` 或 `https://` 开头
4. **token**：API 密钥
5. **模型映射**（可选）：opus / sonnet / haiku 三档分别用什么模型；不知道或不适用就留空（如 OpenRouter 用平台默认）

收齐后运行：

```bash
python <脚本路径> add <key> --name <名称> --base-url <url> --token <token> [--opus <m>] [--sonnet <m>] [--haiku <m>]
```

- 脚本会校验 URL 格式、拦截重复 key（覆盖同名需加 `--force`），写入前自动备份 `model-profiles.json`，原子写入。
- key 已存在时把冲突告诉用户：换一个 key，或确认后加 `--force` 覆盖。
- 成功后告诉用户"已添加提供商 <name>（<key>），要切换到它请回复 /model-switch <key>"。

## 注意

- 脚本输出中的 token 已脱敏（如 `6e13****fdTi`）；回复用户时不要输出完整 token。
- 用户给的 key 不存在时，脚本会打印可用 key，把列表展示给用户让其重选即可。
- `openrouter` 这类没有 `model` 映射的 profile，切换时三个 `DEFAULT_*_MODEL` 变量会被移除（使用平台默认模型），属正常行为。
- 切换不需要确认（用户已明确输入目标 key 时直接执行）；无参数时输出完整表格等用户回复 key，由用户的回复本身承担确认。

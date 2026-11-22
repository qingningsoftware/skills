---
name: model-switch
description: 切换 Claude Code 的模型提供商配置（读写 ~/.claude/model-profiles.json 与 ~/.claude/settings.json）。当用户想切换/更换模型或提供商（如"切换到 glm"、"用 kimi"、"换成千问"、"换回 OpenRouter"、"现在用的什么模型"、"有哪些模型/提供商可用"）、添加新的模型提供商（如"加个提供商"、"添加 kimi 配置"），或输入 /model-switch [list|status|add|<key>] 时，必须使用本 skill。
---

# model-switch — Claude Code 模型提供商切换

配置源是 `~/.claude/model-profiles.json`（每个提供商含 `name`、`baseUrl`、`token`、`model.{opus,sonnet,haiku}`）。切换 = 把选中 profile 的值写入 `~/.claude/settings.json` 的 `env` 中这 5 个变量：`ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_DEFAULT_OPUS_MODEL`、`ANTHROPIC_DEFAULT_SONNET_MODEL`、`ANTHROPIC_DEFAULT_HAIKU_MODEL`。

脚本会自动：每次切换前备份 `settings.json` 到 `settings.json.bak-model-switch`；原子写入；保留其余所有变量（含带 `-glm`/`-qwen` 等后缀的备份变量）不动。

## 脚本位置

本 SKILL.md 同目录下的 `scripts/model_switch.py`（路径相对于本文件解析，个人 skill 与插件两种安装位置均适用）。用 Bash 运行 `python <脚本路径> <命令>`；macOS/Linux 上若提示 `python` 不存在，改用 `python3`（脚本兼容两者）。

## 命令映射

| 用户输入 | 动作 |
|---|---|
| `/model-switch list` | 运行 `python <脚本> list`，把列表展示给用户（token 已脱敏，不要输出完整 token） |
| `/model-switch status` | 运行 `python <脚本> status`，展示当前生效配置 |
| `/model-switch <key>` | 运行 `python <脚本> switch <key>`；成功后告诉用户"当前模型已修改成 <name>（<key>）" |
| `/model-switch official` | 运行 `python <脚本> switch official`；成功后告诉用户"已切回 Claude Code 官方登录，其余配置未动" |
| `/model-switch`（无参数） | 运行 `list`，把全部提供商整理成 markdown 表格输出（含"当前生效"标记），请用户直接回复要切换的 key。不要用 AskUserQuestion 弹窗做选择——它最多只能显示 4 个选项，提供商多于 4 个时必然列不全 |
| `/model-switch add` | 进入添加模式：用 AskUserQuestion **逐项弹窗**录入（每项一个对话框，随时可按 Esc 取消整个流程），全部录完确认后写入。**不要把收到的 token 显示在回复里** |

## 添加提供商（/model-switch add）

逐项弹窗录入，共 5～6 个对话框，**每个都用 AskUserQuestion 单独弹出，用户在"Other"中输入文本**。任一步用户按 Esc 取消（或选"取消录入"），立即终止流程并告知"已取消，未写入任何配置"。

按顺序弹出（**注意：AskUserQuestion 每题必须 ≥2 个选项**，用户在"Other"里输入文本；除第 1 步外每步都可给"重新开始"选项）：

1. **key**：问题"请录入模型提供商 key（切换命令用的短标识，小写英文/数字/连字符）"，选项"自动生成（由名称转小写连字符）"和"取消录入"
2. **名称**：问题"请录入模型提供商名称（显示名，如 GLM、Kimi）"，选项"与 key 相同"和"取消录入"
3. **baseUrl**：问题"请录入 API 地址 baseUrl（必须 http:// 或 https:// 开头）"，选项"重新开始"和"取消录入"
4. **token**：问题"请录入 API token（密钥）"，选项"重新开始"和"取消录入"；拿到后**回复中只显示脱敏形式**
5. **模型映射**（可选）：问题"请录入模型映射（格式如 opus=m1 sonnet=m2 haiku=m3，留空/跳过则用平台默认）"，选项"跳过（用平台默认）"、"三档用同一模型（在 Other 里只填模型名）"和"取消录入"；解析用户输入中的 opus=/sonnet=/haiku= 各档
6. **确认**：汇总展示（token 脱敏、模型映射可省略），问题"确认写入 model-profiles.json 吗？"，选项"确认写入（推荐）"和"取消录入"

用户点 Esc/取消：告知已取消，结束。用户确认后运行：

```bash
python <脚本路径> add <key> --name <名称> --base-url <url> --token <token> [--opus <m>] [--sonnet <m>] [--haiku <m>]
```

- 脚本会校验 URL 格式、拦截重复 key（覆盖同名需加 `--force`），写入前自动备份 `model-profiles.json`，原子写入。
- key 已存在时把冲突告诉用户：换一个 key，或确认后重新执行带 `--force` 的写入。
- 校验失败（URL 格式错等）：只重新弹那一个对话框让用户改，已录入的其他项保留在内存中重试，不必从头再来。
- 成功后告诉用户"已添加提供商 <name>（<key>），要切换到它请回复 /model-switch <key>"。

## 注意

- 脚本输出中的 token 已脱敏（如 `6e13****fdTi`）；回复用户时不要输出完整 token。
- 用户给的 key 不存在时，脚本会打印可用 key，把列表展示给用户让其重选即可。
- `openrouter` 这类没有 `model` 映射的 profile，切换时三个 `DEFAULT_*_MODEL` 变量会被移除（使用平台默认模型），属正常行为。
- 配置目录默认 `~/.claude`；用户设置了 `CLAUDE_CONFIG_DIR` 环境变量时，脚本会自动改读该目录（与 Claude Code 行为一致），无需额外参数。
- 切换不需要确认（用户已明确输入目标 key 时直接执行）；无参数时输出完整表格等用户回复 key，由用户的回复本身承担确认。
- 本 skill 只管 **Claude Code** 的配置（settings.json）。用户要切换 **OpenAI Codex** 的提供商时，请引导其自行在终端运行 `python <脚本路径> codex list|status|switch|add`（零模型，详见仓库 model-switch README 的 Codex 章节），不要代为执行。

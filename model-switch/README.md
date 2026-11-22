# model-switch — 模型提供商一键切换

一个命令行工具（Claude Code 侧同时是插件/skill），给 **Claude Code** 和 **OpenAI Codex（CLI / 桌面版）** 一键切换模型提供商。GLM、千问、Kimi、DeepSeek、OpenRouter 及各类中转均可接入——**地址与密钥由用户自行录入，工具不内置任何供应商信息**。

## 主要功能

- **list**：列出已录入的提供商，标记当前生效
- **status**：查看当前生效配置与匹配的提供商
- **switch \<key\>**：一键切换到指定提供商
- **switch official**：切回官方登录（Claude Code = 移除脚本托管的 `ANTHROPIC_*` 变量；Codex = 删除 `model_provider` 行），其余配置原样保留
- **add**：添加提供商，可选代设环境变量（已有变量不静默覆盖）
- 每次修改前自动备份，写入用临时文件 + 原子替换，改后做语法校验
- **零第三方依赖、零模型依赖**：纯 Python 标准库，终端直接运行，不经过任何模型

## 支持的操作系统

Windows / macOS / Linux（需 Python 3.11+）。macOS/Linux 若无 `python` 命令，把命令中的 `python` 换成 `python3`。

## 支持的工具

| 宿主 | 调用方式 | 改哪个配置 |
|---|---|---|
| Claude Code | 插件 skill：`/model-switch ...`；或终端脚本 | `~/.claude/settings.json` 的 `env` |
| OpenAI Codex（CLI / 桌面版） | 终端脚本 `codex` 子命令；也可装成 Codex skill | `~/.codex/config.toml` |

> 两边协议不同（Claude Code 走 Anthropic 协议、Codex 走 OpenAI 协议），同一提供商在两边的 base_url 不同、token 通用——具体地址请向你的提供商确认。

## 安装

### Claude Code — 插件市场（推荐）

在 Claude Code 会话内输入：

```
/plugin marketplace add qingningsoftware/skills
/plugin install model-switch@qingning-skills
```

或在终端用 CLI 安装：

```bash
claude plugin marketplace add qingningsoftware/skills
claude plugin install model-switch@qingning-skills
```

安装后重启 Claude Code，输入 `/model-switch` 即可使用。后续更新：`/plugin marketplace update qingning-skills`。

### Claude Code — 手动安装为个人 skill

把仓库中 `model-switch/skills/model-switch/` 整个目录复制到 `~/.claude/skills/model-switch/`（Windows 即 `C:\Users\<用户名>\.claude\skills\`），重启 Claude Code 后生效。

### OpenAI Codex — 直接终端运行，无需安装

clone 本仓库后用路径调用即可（见下文使用方法）。若想让 **Codex 会话里**也能调用，把 skill 拷进 Codex 的 skill 目录（Git Bash / macOS / Linux）：

```bash
git clone --depth 1 https://github.com/qingningsoftware/skills /tmp/qn-skills
mkdir -p ~/.codex/skills/codex-switch/scripts
cp /tmp/qn-skills/model-switch/codex-skill/SKILL.md ~/.codex/skills/codex-switch/SKILL.md
cp /tmp/qn-skills/model-switch/skills/model-switch/scripts/model_switch.py \
   /tmp/qn-skills/model-switch/skills/model-switch/scripts/codex_switch.py \
   ~/.codex/skills/codex-switch/scripts/
rm -rf /tmp/qn-skills
```

Windows PowerShell 版：

```powershell
git clone --depth 1 https://github.com/qingningsoftware/skills "$env:TEMP\qn-skills"
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills\codex-switch\scripts" | Out-Null
Copy-Item "$env:TEMP\qn-skills\model-switch\codex-skill\SKILL.md" "$env:USERPROFILE\.codex\skills\codex-switch\"
Copy-Item "$env:TEMP\qn-skills\model-switch\skills\model-switch\scripts\*.py" "$env:USERPROFILE\.codex\skills\codex-switch\scripts\"
Remove-Item -Recurse -Force "$env:TEMP\qn-skills"
```

装完重启 Codex，在已安装技能里确认；也可直接在对话里问"我现在 Codex 用哪个提供商"验证。

## 使用方法

### Claude Code

**会话内（安装插件后）**：

| 命令 | 作用 |
|---|---|
| `/model-switch` | 列出所有提供商，选完直接切换 |
| `/model-switch list` | 列出提供商（标记当前生效，token 脱敏） |
| `/model-switch status` | 查看当前 `settings.json` 生效配置 |
| `/model-switch add` | 逐项弹窗录入 key/名称/baseUrl/token/模型映射 |
| `/model-switch \<key\>` | 直接切换，如 `/model-switch glm` |
| `/model-switch official` | 切回 Claude Code 官方登录 |

**终端**：

```bash
python <脚本路径>/model_switch.py list
python <脚本路径>/model_switch.py status
python <脚本路径>/model_switch.py switch glm
python <脚本路径>/model_switch.py switch official
python <脚本路径>/model_switch.py add my-provider \
  --name "My Provider" --base-url https://api.example.com/anthropic \
  --token sk-xxx --opus m1 --sonnet m2 --haiku m3   # 模型映射可选，覆盖同名加 --force
```

可选参数：`--profiles <path>` 指定 model-profiles.json 路径；`--settings <path>` 指定 settings.json 路径（测试时有用）。

**配置文件**：`~/.claude/model-profiles.json` 是唯一配置源（可复制仓库里的 `model-profiles.example.json` 改）：

```json
{
  "my-provider": {
    "name": "显示名称",
    "baseUrl": "<提供商的 Anthropic 协议地址>",
    "token": "你的 API Token",
    "model": { "opus": "m1", "sonnet": "m2", "haiku": "m3" }
  }
}
```

- 顶层 key 就是切换命令用的 `<key>`；`model` 三档对应 Opus/Sonnet/Haiku，留空则用平台默认。
- 切换 = 把选中 profile 写入 `settings.json` 的 `env` 中 5 个变量：`ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_DEFAULT_OPUS_MODEL` / `SONNET` / `HAIKU`；其余变量原样保留。
- 设置了 `CLAUDE_CONFIG_DIR` 环境变量时，脚本自动改读该目录（与 Claude Code 行为一致）。

### OpenAI Codex（codex 子命令，零模型）

```bash
python <脚本路径>/model_switch.py codex list               # 列出提供商，标记当前生效
python <脚本路径>/model_switch.py codex status             # 查看当前 model / model_provider
python <脚本路径>/model_switch.py codex switch glm         # 切换（可加 --model <模型id>）
python <脚本路径>/model_switch.py codex switch official    # 切回 OpenAI 官方（ChatGPT 登录）
python <脚本路径>/model_switch.py codex add <key> \
    --name <名称> --base-url <提供商的OpenAI兼容地址> --env-key <变量名> \
    [--wire-api chat|responses] [--set-env-var <token>]
```

- 提供商定义常驻 `~/.codex/config.toml` 的 `[model_providers.<key>]` 小节，切换只改顶部 `model` / `model_provider` 两行，其余内容逐行保留；key 本体存环境变量（每家一个独立变量名、设一次常驻），切换永不碰环境变量。
- `add` 可选：`--wire-api chat|responses`（默认 chat）；`--set-env-var <token>` 代跑 `setx`；`--force` 覆盖同名提供商；`--force-env` 允许覆盖已存在的环境变量。
- **切换后必须完全退出（含托盘）并重启 Codex**（Codex 启动时读配置）；`setx` 对新启动的进程生效，旧终端里再开的子进程仍是旧值。
- 首次修改前把 `config.toml`、`auth.json` 和现有 key 变量值快照到 `~/.codex/backup-<时间戳>/`（`env-snapshot.json` 含明文 key，勿外传），此后每次修改前追加备份副本。
- 在 Codex 会话里通过 skill 调用本工具会走一次模型；**零模型路径始终是终端直接运行脚本**，两者并存不冲突。

## 安全机制

- **自动备份**：Claude 侧切换前备份 `settings.json`、添加前备份 `model-profiles.json`；Codex 侧见上。
- **原子写入**：先写临时文件再替换，中途失败不损坏配置。
- **最小改动**：只改脚本托管的变量/行，其余配置（含带后缀的备份变量、注释、Codex 自有小节）原样保留。
- **token 脱敏**：所有输出只显示 token 头尾，防止截图泄露。
- token 与配置文件均属敏感信息，不要提交到公共仓库或截图分享。

## 文件清单

```
skills/                  # GitHub 仓库 qingningsoftware/skills = 插件市场仓库
├── .claude-plugin/
│   └── marketplace.json   # 市场清单（市场名 qingning-skills，列出各插件）
├── README.md                 # 市场说明 + 安装命令
└── model-switch/             # 本插件（一个 skill 一个文件夹）
    ├── .claude-plugin/
    │   ├── plugin.json           # 插件清单
    │   └── icon.png              # 插件图标
    ├── skills/
    │   └── model-switch/
    │       ├── SKILL.md                  # skill 定义（Claude Code 读取的触发与执行说明）
    │       ├── model-profiles.example.json  # 配置模板（复制为 ~/.claude/model-profiles.json 后填 token）
    │       └── scripts/
    │           ├── model_switch.py       # 切换脚本（Python 3 标准库，无第三方依赖）
    │           └── codex_switch.py       # Codex 后端（经 model_switch.py codex 调用，也可独立运行）
    ├── codex-skill/           # Codex 版 SKILL.md（分发给其他用户拷到 ~/.codex/skills/codex-switch/）
    ├── tests/                 # pytest 测试（Codex 后端与宿主分发）
    ├── LICENSE                # MIT 许可证
    ├── .gitignore
    └── README.md              # 本说明文档
```

## License

[MIT](LICENSE)

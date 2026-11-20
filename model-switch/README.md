# model-switch — Claude Code 模型提供商切换

一个 Claude Code 插件/skill，用于在命令行快速切换 Claude Code 使用的模型提供商（GLM、Qwen、Kimi、DeepSeek、OpenRouter 等），无需手动编辑 `settings.json`。每次切换自动备份、原子写入、保留其余配置，token 全程脱敏显示。

## 功能

| 命令 | 作用 |
|---|---|
| `/model-switch` | 列出所有提供商，选完直接切换 |
| `/model-switch list` | 列出所有提供商（标记当前生效，token 脱敏显示） |
| `/model-switch status` | 查看当前 `settings.json` 生效配置及匹配的提供商 |
| `/model-switch <key>` | 直接切换，如 `/model-switch glm`、`/model-switch kimi` |

也可以绕过 Claude 直接在终端运行脚本：

```bash
python ~/.claude/skills/model-switch/scripts/model_switch.py list
python ~/.claude/skills/model-switch/scripts/model_switch.py status
python ~/.claude/skills/model-switch/scripts/model_switch.py switch glm
# 可选参数：
#   --profiles <path>  指定 model-profiles.json 路径
#   --settings <path>  指定 settings.json 路径（测试时很有用）
```

## 安装

### 方式一：插件市场安装（推荐）

在 Claude Code 会话内输入：

```
/plugin marketplace add asdf112255/skills
/plugin install model-switch@zhuyi-skills
```

或在终端用 CLI 安装：

```bash
claude plugin marketplace add asdf112255/skills
claude plugin install model-switch@zhuyi-skills
```

安装后重启 Claude Code，输入 `/model-switch` 即可使用。后续更新：

```
/plugin marketplace update zhuyi-skills
```

### 方式二：手动安装为个人 skill

把仓库中 `skills/model-switch/` 整个目录复制到 `~/.claude/skills/model-switch/`（Windows 即 `C:\Users\<用户名>\.claude\skills\`），重启 Claude Code 后生效。

### 首次使用

1. 复制仓库中的 `skills/model-switch/model-profiles.example.json` 为 `~/.claude/model-profiles.json`；
2. 把 token 换成你自己的 API Token（按同样格式可添加任意多个提供商）；
3. 重启 Claude Code，运行 `/model-switch list` 确认。

## 配置文件

### ~/.claude/model-profiles.json（唯一配置源，手动维护）

```json
{
  "glm": {
    "name": "GLM",
    "baseUrl": "https://open.bigmodel.cn/api/anthropic",
    "token": "你的 API Token",
    "model": {
      "opus": "glm-5.3",
      "sonnet": "glm-5.3-flash",
      "haiku": "glm-5.3-flash"
    }
  }
}
```

- 顶层 key 就是切换命令用的 `<key>`（如 `glm`、`qwen`、`kimi`），可随时增删。
- `model` 三档分别对应 Claude Code 的 Opus/Sonnet/Haiku 档位映射。
- 某档留空或整个 `model` 留空 `{}` 时，切换后该档的 `ANTHROPIC_DEFAULT_*_MODEL` 变量会被移除，使用该平台的默认模型（如 `openrouter`）。

### ~/.claude/settings.json（脚本自动改写）

切换 = 把选中 profile 的值写入其 `env` 中的 5 个变量：

- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_AUTH_TOKEN`
- `ANTHROPIC_DEFAULT_OPUS_MODEL` / `ANTHROPIC_DEFAULT_SONNET_MODEL` / `ANTHROPIC_DEFAULT_HAIKU_MODEL`

## 安全机制

- **自动备份**：每次切换前把 `settings.json` 备份到 `settings.json.bak-model-switch`（同目录，覆盖式快照）。
- **原子写入**：先写临时文件再替换，中途失败不会损坏配置。
- **最小改动**：`env` 中其余变量（包括 `ANTHROPIC_AUTH_TOKEN-glm` 这类带后缀的备份变量）一律原样保留；`env` 以外的配置完全不动。
- **token 脱敏**：`list`/`status` 输出只显示 token 头尾（如 `6e136****fdTi`），防止截图泄露。
- **当前生效标记**：`list` 按 baseUrl + token（必要时再比对三档模型）识别当前生效的提供商并标记 `<-- 当前生效`。

## 注意

- 切换写入的是 `settings.json`，配置修改立即生效。skill 执行切换后会提示"当前模型已修改成 <name>（<key>）"。
- token 属敏感信息：`model-profiles.json` 和 `settings.json` 都不要提交到公共仓库或截图分享。

## 文件清单

```
skills/                        # GitHub 仓库 asdf112255/skills = 插件市场仓库
├── .claude-plugin/
│   └── marketplace.json      # 市场清单（市场名 zhuyi-skills，列出各插件）
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
    │           └── model_switch.py       # 切换脚本（Python 3 标准库，无第三方依赖）
    ├── LICENSE                # MIT 许可证
    ├── .gitignore
    └── README.md              # 本说明文档
```

## License

[MIT](LICENSE)

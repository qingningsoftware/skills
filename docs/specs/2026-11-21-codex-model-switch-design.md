# codex-switch — Codex 模型提供商切换 CLI · 设计方案

日期：2026-11-21 起草；2026-11-22 定案（形态、存储模型、备份规则已确认，待实施）

## 背景与目标

仓库已有 Claude Code 版 model-switch 插件（`model-switch/`），通过改写 `~/.claude/settings.json` 的 `env` 实现一键切换模型提供商。现给 OpenAI Codex（CLI / 桌面版）做同等能力：一键切换提供商（GLM/千问/Kimi/OpenRouter 及中转等），并支持一键切回 OpenAI 官方。

## 已查明的事实

### 2026-11-21 实测（Windows 11 + Codex 桌面版 26.1117）

- 配置文件：`~/.codex/config.toml`（TOML）；认证在 `~/.codex/auth.json`（ChatGPT OAuth 登录，`OPENAI_API_KEY` 字段为空 = 从没配过 API key）；skill 目录 `~/.codex/skills/`
- 界面里的模型列表（gpt-6-luna / gpt-5.6-terra / gpt-5.6-luna）来自服务端下发的 `~/.codex/models_cache.json`，与 config.toml 无关；config.toml 顶部的 `model = "..."` 只是记录当前选中项
- **切换机制**：改 config.toml 顶部两行 `model` + `model_provider`；提供商定义写在 `[model_providers.<key>]` 小节（`name` / `base_url` / `env_key` / `wire_api`）
- **key 不进配置文件**：`env_key` 只写环境变量名，token 要设到系统环境变量（Windows `setx`），对新启动的进程生效（桌面版需重启 Codex）
- **协议差异（关键）**：Codex 走 OpenAI 协议（`wire_api = "chat"` 或 `"responses"`），Claude Code 走 Anthropic 协议。同一家提供商两边 base_url 不同，token 通用
- 现有中转 jtzn-glm（hbjt）是 Anthropic 协议，是否有 OpenAI 兼容端点**待确认**

### 2026-11-22 实测（本机 config.toml 现状）

- 当前**无**任何 `[model_providers.*]` 小节、**无** `model_provider` 行——正在使用 ChatGPT 官方登录，没有自定义供应商和 key 在用
- config.toml 混有大量 Codex 自有小节（`[marketplaces.*]`、`[plugins.*]`、`[projects.*]`、`[mcp_servers.*]`、`[windows]`、`[desktop]` 等），含 `\\?\` 前缀、单引号 literal string 等特殊 TOML 语法
- 由此定案：**绝不能整文件重序列化**，只能对目标行/小节做文本精准编辑

## 形态定案（2026-11-22）

**独立 CLI**：仓库根新增 `codex-switch/` 目录（`codex_switch.py` + `README.md`），**不做** Claude Code skill、**不做**市场插件壳。

理由：slash command / skill 的调用本质是"把提示词发给模型、由模型执行"，任何宿主（Claude Code、Codex CLI/桌面版）都一样，调用必然经过一次模型；本工具要求切换操作**零模型依赖**——尤其在当前供应商挂掉时，仍能不依赖任何可用模型完成切换（自救）。日后若需要 `/codex-switch` 入口，补一个 command md 文件即可，随时可加。

> **2026-11-22 修订**：应用户要求统一入口，Codex 逻辑并入 model-switch 插件——`model_switch.py codex ...` 子命令（`codex_switch.py` 作为后端模块随插件分发，仍可独立运行），`codex-switch/` 独立目录取消。零模型 CLI 形态不变；Claude 侧同时补齐对称的 `switch official`（切回官方登录）。

## 存储模型（无 json 底册）

| 内容 | 存哪 |
|---|---|
| 提供商定义（name / base_url / env_key / wire_api） | `config.toml` 的 `[model_providers.*]` 小节（全部候选常驻） |
| 当前选中哪家 | `config.toml` 顶部 `model` + `model_provider` 两行（`model_provider` 当前不存在，首次添加供应商时在顶部区域插入） |
| API key 本体 | 环境变量（`setx` 写注册表 HKCU\Environment），每家一个**独立变量名**，设一次常驻 |
| ChatGPT 官方登录态 | `~/.codex/auth.json`，工具不碰 |

规则：

- **switch 永不碰环境变量**，只改顶部两行；切回官方 = 删除/注释 `model_provider` 行（走 ChatGPT 登录，无需 key）
- **add** 录入提供商并可选代跑 `setx`（本地操作，无需模型）；若目标变量名已存在，提示确认、不静默覆盖
- 对比：Claude 版需要 `model-profiles.json` 是因为 `settings.json` 没有放候选列表的位置；Codex 的 toml 天生有 `[model_providers.*]`，**不需要 json 底册**

## 备份设计（硬性规则）

1. **首次运行**（任何修改前）一次性快照到 `~/.codex/backup-<YYYYMMDD-HHMMSS>/`：
   - `config.toml` 原样副本
   - `auth.json` 原样副本（运行期本就不碰，纯保险）
   - `env-snapshot.json`：现有 `[model_providers.*]` 中 `env_key` 引用的变量名 → 当前值；用 `winreg` 读注册表真值，不读进程环境（setx 后进程环境可能过期）。当前无自定义供应商时为空表
2. **此后每次修改** config.toml 前自动向同一目录追加时间戳副本；写入用临时文件 + 原子替换
3. `env-snapshot.json` 含明文 key：仅存本机 `~/.codex` 下，不入 git、不外传

## 命令设计

风格复用 `model_switch.py`：`list` / `status` / `switch` / `add`，自动备份、原子写入、token 脱敏显示、支持 `CODEX_HOME` 覆盖 `~/.codex`。

- `switch <名称或序号>`：文本精准编辑顶部两行；打印切换结果与重启提示（Codex 启动时读配置，需完全退出含托盘再重开）
- `add`：逐项录入 key 名称、name、base_url、env_key 变量名、wire_api（chat/responses），可选代设环境变量
- `status`：显示当前提供商、各候选及对应变量是否已设置（只报有无，不显示值）

## TOML 写入方式（定案）

只精准编辑目标行/小节（顶部两行、`[model_providers.*]` 小节的增删改），保留全部注释与结构；Python 3.11+ `tomllib`（只读）用于改后语法校验，零第三方依赖。

## 仍开放（2026-11-22 更新）

- **hbjt 双协议：已确认**（用户提供 OpenAI 兼容端点）：
  - hbjt-glm：`http://hbjt.com/service-GLM-53-falsh-test/v1/chat/completions`（Codex base_url 取 `.../v1`）
  - hbjt-dsv41：`http://hbjt.com/service-deepseekv41flash/test/v1/chat/completions`（同上）
  - 注意：`falsh` 疑似 `flash` 笔误，按用户原文记录，联调 404 时先核对路径
- 内置提供商（GLM/千问/Kimi/DeepSeek/OpenRouter）base_url：官方文档联网核对被网络策略拦截，model-switch README 已列参考值（标注未复核）+ curl 自测法
- 已实现：Claude 侧 `switch official`（切回官方登录，与 Codex 侧对称）；内置清单不写死进代码，维持 add 手工录入 + README 参考表

## 原草案待定问题的归宿

1. 接入哪些提供商 → 仍开放（见上，不阻塞）
2. token 管理方式 → 每家独立变量设一次常驻；add 可代设，已有变量不静默覆盖
3. 插件形态 → 独立 CLI，无 skill、无插件壳（理由见"形态定案"）
4. 配置源 → 直接读写 config.toml 的 `[model_providers.*]`，无 json 底册
5. TOML 写入方式 → 文本精准编辑 + tomllib 只读校验（2026-11-22 实测定案）

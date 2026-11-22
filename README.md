# qingning-skills

Claude Code 插件市场仓库，每个文件夹是一个独立 skill 插件。

## Skills

| 插件 | 主要功能 |
|---|---|
| [model-switch](model-switch/) | 切换模型提供商（GLM/Qwen/Kimi/DeepSeek/OpenRouter 等）：Claude Code 侧经 skill 一键切换/弹窗添加；OpenAI Codex 侧用终端 `codex` 子命令（零模型），自动备份、原子写入、token 脱敏 |

## 安装

```
/plugin marketplace add qingningsoftware/skills
/plugin install <插件名>@qingning-skills
```


详细使用说明见各插件目录内的 README。

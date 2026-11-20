# zhuyi-skills — Claude Code 插件市场

zhuyi 的 Claude Code skill 合集仓库，同时是一个插件市场（marketplace）。仓库根下每个文件夹是一个独立插件，可单独安装。

## 收录的插件

| 插件 | 说明 |
|---|---|
| [model-switch](model-switch/) | 命令行快速切换 Claude Code 模型提供商（GLM/Qwen/Kimi/DeepSeek/OpenRouter 等），自动备份、原子写入、token 脱敏 |

## 安装

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

安装后重启 Claude Code 即可使用。

## 更新

插件作者推送新版本后，用户执行：

```
/plugin marketplace update zhuyi-skills
```

## 如何新增一个技能插件

1. 在仓库根新建 `<skill-name>/` 文件夹，内含：
   - `.claude-plugin/plugin.json`（插件清单）
   - `skills/<skill-name>/SKILL.md`（skill 定义，Claude Code 自动发现）
2. 在 `.claude-plugin/marketplace.json` 的 `plugins` 数组中追加：
   ```json
   { "name": "<skill-name>", "description": "一句话说明", "source": "./<skill-name>" }
   ```
3. 提交推送后，用户执行 `/plugin marketplace update zhuyi-skills` 即可获取。

## License

各插件目录内分别附带许可证（model-switch 为 MIT）。

# AI CLI - OpenAI兼容API流式客户端

一个支持流式响应的OpenAI兼容API命令行客户端，具有历史记录功能。

## 功能特性

- 🔄 **流式响应**: 实时显示AI回复，无需等待完整响应
- 📝 **历史记录**: 支持上下箭头键浏览历史输入记录
- 💾 **持久化存储**: 历史记录自动保存到 `~/.ai_cli_history`
- 🔧 **灵活配置**: 支持自定义API地址、模型和密钥
- 🛡️ **错误处理**: 智能处理编码问题和网络错误
- ⚡ **性能统计**: 显示响应时间和Token处理速度

## 安装要求

```bash
pip install requests
```

## 环境变量配置

程序支持通过 `.env` 文件配置环境变量，按照以下优先级顺序：

1. **当前目录的 `.env` 文件**（优先级最高）
2. **用户目录的 `~/.env` 文件**（如果当前目录没有 `.env`）

### 支持的环境变量

| 环境变量 | 说明 | 示例 |
|----------|------|------|
| `AI_CLI_BASE_URL` 或 `OPENAI_BASE_URL` | API基础URL | `http://localhost:7867` |
| `AI_CLI_MODEL` 或 `OPENAI_MODEL` | 模型名称 | `Qwen3` |
| `AI_CLI_API_KEY` 或 `OPENAI_API_KEY` | API密钥 | `your-api-key` |

### 配置文件示例

创建 `.env` 文件：

```bash
# API基础URL
AI_CLI_BASE_URL=http://localhost:7867

# 模型名称
AI_CLI_MODEL=Qwen3

# API密钥（可选）
AI_CLI_API_KEY=your-api-key-here
```

**注意**: 程序同时支持 `AI_CLI_*` 和 `OPENAI_*` 前缀的环境变量，优先使用 `AI_CLI_*` 前缀。

## 使用方法

### 基本使用

```bash
python3 ai-cli.py
```

### 自定义配置

配置优先级（从高到低）：
1. 命令行参数
2. 环境变量（`.env` 文件）
3. 默认值

```bash
# 指定不同的API地址
python3 ai-cli.py --base_url http://your-api-server:7867

# 指定模型名称
python3 ai-cli.py --model your-model-name

# 指定API密钥
python3 ai-cli.py --api_key your-api-key

# 组合使用
python3 ai-cli.py --base_url http://localhost:7867 --model Qwen3 --api_key sk-xxx
```

### 历史记录功能

- **上下箭头键**: 浏览历史输入记录
- **Tab键**: 自动补全（如果支持）
- **历史记录文件**: `~/.ai_cli_history`
- **历史记录长度**: 最多保存1000条记录

### 退出程序

输入以下任一命令退出程序：
- `/quit`
- `/exit`
- `/bye`

或使用 `Ctrl+C`

## 配置说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--base_url` | `http://localhost:7867` | API服务器地址 |
| `--model` | `Qwen3` | 模型名称 |
| `--api_key` | 空 | API密钥（可选） |

## 性能统计

程序会显示以下性能信息：
- 总处理时间
- 总Token数
- Token处理速度 (TPS)

## 注意事项

1. 确保API服务器正在运行且可访问
2. 历史记录文件会自动创建和更新
3. 支持中文输入和显示
4. 网络超时设置为30秒

## 故障排除

### 历史记录不工作
- 检查是否安装了 `readline` 模块
- 确认终端支持readline功能

### 连接错误
- 检查API服务器是否运行
- 验证 `--base_url` 参数是否正确
- 确认网络连接正常

### 编码问题
- 程序会自动尝试修复编码错误
- 如果问题持续，请检查终端编码设置 
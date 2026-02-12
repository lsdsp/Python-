# Python 划词助手

一个基于 **Python 标准库 HTTP 服务 + 原生 JavaScript + 托盘应用** 的划词助手示例。

## 新增桌面端行为

- 首次运行会自动弹出配置界面。
- 关闭配置界面后，程序不会退出，而是最小化到系统托盘。
- 右键托盘图标可选择：
  - **配置**：重新打开配置界面。
  - **退出**：完全退出程序（停止 HTTP 服务 + 退出进程）。

## 功能

当你在页面中选中文本时，会在选中文字上方浮现操作提示框，提供四个功能：

- 翻译（优先调用 uapis `POST /api/v1/ai/translate`，失败自动降级到 `POST /api/v1/translate/text`）
- 解释（解释含义）
- 搜索（调用 OpenAI 兼容接口生成 AI 搜索结果）
- 复制

## 安装与运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

浏览器访问：`http://127.0.0.1:5000`

## 配置文件

配置会保存在：`~/.selection_assistant_config.json`

## 环境变量（由配置界面写入）

- `UAPIS_API_KEY`
- `UAPIS_TRANSLATE_FROM`（默认 `auto`）
- `UAPIS_TRANSLATE_TO`（默认 `zh-CHS`）
- `UAPIS_TRANSLATE_STYLE`（默认 `professional`）
- `UAPIS_TRANSLATE_CONTEXT`（默认 `general`）
- `UAPIS_PRESERVE_FORMAT`（默认 `true`）
- `UAPIS_FAST_MODE`（默认 `false`）
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`（默认 `https://api.openai.com/v1`）
- `OPENAI_SEARCH_MODEL`（默认 `gpt-4o-mini`）

## 说明

- `/api/translate`：
  - 主链路：`POST /api/v1/ai/translate?target_lang=...`，Body 发送 `text/source_lang/style/context/preserve_format/fast_mode`。
  - 失败回退：`POST /api/v1/translate/text?to_lang=...`，Body 发送 `text`。
- `/api/explain`：提供词语含义解释（内置少量词条，其他词提供通用解释）。
- `/api/search`：通过 OpenAI 兼容 `chat/completions` 接口生成 `title/summary/url` 结构化结果。

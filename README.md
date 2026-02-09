# Python 划词助手

一个基于 **Python 标准库 HTTP 服务 + 原生 JavaScript** 的划词助手示例。

## 功能

当你在页面中选中文本时，会在选中文字上方浮现操作提示框，提供四个功能：

- 翻译
- 解释（解释含义）
- 搜索（AI 搜索跳转）
- 复制

## 运行方式

```bash
python -m venv .venv
source .venv/bin/activate
python app.py
```

浏览器访问：`http://127.0.0.1:5000`

## 说明

- `/api/translate`：提供简单演示翻译（内置少量词典，其他词回显演示结果）。
- `/api/explain`：提供词语含义解释（内置少量词条，其他词提供通用解释）。
- `/api/search`：返回 AI 搜索链接（默认 `https://www.perplexity.ai/search?q=`，可通过环境变量 `AI_SEARCH_URL` 覆盖）。

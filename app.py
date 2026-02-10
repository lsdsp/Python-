from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = BASE_DIR / "templates" / "index.html"

TRANSLATION_MAP = {
    "hello": "你好",
    "world": "世界",
    "python": "Python（一种编程语言）",
    "assistant": "助手",
}

EXPLANATION_MAP = {
    "hello": "常见英文问候语，用于打招呼。",
    "world": "通常表示‘世界’或某个整体领域。",
    "python": "一种流行的高级编程语言，强调可读性与开发效率。",
    "assistant": "指提供帮助、建议或执行辅助任务的角色。",
}


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


class SelectionAssistantHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self.serve_index()
            return

        if parsed.path.startswith("/static/"):
            self.path = "/" + parsed.path.removeprefix("/static/")
            return super().do_GET()

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def list_directory(self, path):
        self.send_error(HTTPStatus.FORBIDDEN, "Directory listing is disabled")
        return None

    def serve_index(self):
        if not INDEX_FILE.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        try:
            data = INDEX_FILE.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Internal Server Error")
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/translate", "/api/explain", "/api/search"}:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({"error": "invalid json"}, HTTPStatus.BAD_REQUEST)
            return

        text = normalize_text(str(payload.get("text", "")))
        if not text:
            self.send_json({"error": "text is required"}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/translate":
            response = {
                "source": text,
                "translation": TRANSLATION_MAP.get(text.lower(), f"（演示）{text}"),
            }
        elif parsed.path == "/api/explain":
            response = {
                "source": text,
                "explanation": EXPLANATION_MAP.get(
                    text.lower(),
                    f"“{text}” 的含义需要结合上下文来判断；这里给出通用解释：它是你当前选中的文本内容。",
                ),
            }
        else:
            ai_url = os.getenv("AI_SEARCH_URL", "https://www.perplexity.ai/search?q=")
            response = {
                "source": text,
                "title": f"AI 搜索：{text}",
                "summary": "点击下方链接可在 AI 搜索工具中继续深度检索。",
                "url": f"{ai_url}{text.replace(' ', '+')}",
            }

        self.send_json(response, HTTPStatus.OK)

    def send_json(self, payload: dict, status: HTTPStatus):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 5000), SelectionAssistantHandler)
    print("Server running at http://127.0.0.1:5000")
    server.serve_forever()

from __future__ import annotations

import json
import os
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request
from urllib.parse import urlencode, urlparse

import pystray
import tkinter as tk
from PIL import Image, ImageDraw
from pystray import MenuItem as item

BASE_DIR = Path(__file__).parent
CONFIG_PATH = Path.home() / ".selection_assistant_config.json"

EXPLANATION_MAP = {
    "hello": "常见英文问候语，用于打招呼。",
    "world": "通常表示‘世界’或某个整体领域。",
    "python": "一种流行的高级编程语言，强调可读性与开发效率。",
    "assistant": "指提供帮助、建议或执行辅助任务的角色。",
}


DEFAULT_CONFIG = {
    "UAPIS_API_KEY": "",
    "UAPIS_TRANSLATE_FROM": "auto",
    "UAPIS_TRANSLATE_TO": "zh-CHS",
    "UAPIS_TRANSLATE_STYLE": "professional",
    "UAPIS_TRANSLATE_CONTEXT": "general",
    "UAPIS_PRESERVE_FORMAT": "true",
    "UAPIS_FAST_MODE": "false",
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "https://api.openai.com/v1",
    "OPENAI_SEARCH_MODEL": "gpt-4o-mini",
}


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def load_config() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG.copy()
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return DEFAULT_CONFIG.copy()

    config = DEFAULT_CONFIG.copy()
    for key in DEFAULT_CONFIG:
        if key in loaded:
            config[key] = str(loaded[key])
    return config


def save_config(config: dict[str, str]) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_config_to_env(config: dict[str, str]) -> None:
    for key, value in config.items():
        os.environ[key] = value


def post_json(url: str, payload: object, headers: dict[str, str], timeout: int = 20):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        req.add_header(key, value)

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            try:
                return json.loads(data)
            except json.JSONDecodeError as exc:
                preview = data.strip().replace("\n", " ")[:200]
                status = getattr(resp, "status", "unknown")
                raise RuntimeError(f"HTTP {status}: invalid json response: {preview}") from exc
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {detail or exc.reason}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"request failed: {exc.reason}") from exc


def find_translation_text(payload: object) -> str:
    if isinstance(payload, str):
        return payload.strip()

    if isinstance(payload, dict):
        for key in ["translation", "translatedText", "translated_text", "target_text", "targetText", "text", "dst", "result", "data"]:
            if key in payload:
                found = find_translation_text(payload[key])
                if found:
                    return found
        for value in payload.values():
            found = find_translation_text(value)
            if found:
                return found

    if isinstance(payload, list):
        for item in payload:
            found = find_translation_text(item)
            if found:
                return found

    return ""


def uapis_auth_headers(api_key: str) -> dict[str, str]:
    return {"X-API-Token": api_key, "Authorization": f"Bearer {api_key}"}


def call_uapis_ai_translate(base_url: str, api_key: str, text: str, source_lang: str, target_lang: str) -> str:
    url = f"{base_url}?{urlencode({'target_lang': target_lang})}"
    payload = {
        "text": text,
        "source_lang": source_lang,
        "style": os.getenv("UAPIS_TRANSLATE_STYLE", "professional"),
        "context": os.getenv("UAPIS_TRANSLATE_CONTEXT", "general"),
        "preserve_format": os.getenv("UAPIS_PRESERVE_FORMAT", "true").lower() != "false",
        "fast_mode": os.getenv("UAPIS_FAST_MODE", "false").lower() == "true",
    }
    result = post_json(url, payload, uapis_auth_headers(api_key))
    translated = find_translation_text(result.get("data", result) if isinstance(result, dict) else result)
    if not translated:
        raise RuntimeError("AI翻译接口未返回可用译文")
    return translated


def call_uapis_text_translate(base_url: str, api_key: str, text: str, target_lang: str) -> str:
    url = f"{base_url}?{urlencode({'to_lang': target_lang})}"
    result = post_json(url, {"text": text}, uapis_auth_headers(api_key))
    translated = find_translation_text(result)
    if not translated:
        raise RuntimeError("机器翻译接口未返回可用译文")
    return translated


def translate_with_uapis(text: str) -> str:
    api_key = os.getenv("UAPIS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少 UAPIS_API_KEY 配置")

    source_lang = os.getenv("UAPIS_TRANSLATE_FROM", "auto")
    target_lang = os.getenv("UAPIS_TRANSLATE_TO", "zh-CHS")
    primary_url = os.getenv("UAPIS_AI_TRANSLATE_URL", "https://uapis.cn/api/v1/ai/translate")
    fallback_url = os.getenv("UAPIS_TEXT_TRANSLATE_URL", "https://uapis.cn/api/v1/translate/text")

    errors: list[str] = []
    try:
        return call_uapis_ai_translate(primary_url, api_key, text, source_lang, target_lang)
    except RuntimeError as exc:
        errors.append(f"{primary_url}: {exc}")

    try:
        return call_uapis_text_translate(fallback_url, api_key, text, target_lang)
    except RuntimeError as exc:
        errors.append(f"{fallback_url}: {exc}")

    raise RuntimeError("；".join(errors) or "UAPIS 翻译调用失败")


def search_with_openai_compatible(text: str) -> dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY 配置")

    url = f"{os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')}/chat/completions"
    payload = {
        "model": os.getenv("OPENAI_SEARCH_MODEL", "gpt-4o-mini"),
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "你是 AI 搜索助手。请基于用户查询返回简洁结论，并尽量提供一个可访问的参考链接。"},
            {"role": "user", "content": f"请对下面的查询进行AI搜索并返回 JSON，字段必须是 title、summary、url。如果没有合适链接，url 返回空字符串。查询：{text}"},
        ],
        "response_format": {"type": "json_object"},
    }
    result = post_json(url, payload, {"Authorization": f"Bearer {api_key}"})
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
    try:
        structured = json.loads(content)
    except json.JSONDecodeError:
        structured = {}
    return {
        "title": str(structured.get("title", "")).strip() or f"AI 搜索：{text}",
        "summary": str(structured.get("summary", "")).strip() or "未返回搜索摘要。",
        "url": str(structured.get("url", "")).strip(),
    }


class SelectionAssistantHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.path = "/templates/index.html"
        return super().do_GET()

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

        try:
            if parsed.path == "/api/translate":
                response = {"source": text, "translation": translate_with_uapis(text)}
            elif parsed.path == "/api/explain":
                response = {
                    "source": text,
                    "explanation": EXPLANATION_MAP.get(text.lower(), f"“{text}” 的含义需要结合上下文来判断；这里给出通用解释：它是你当前选中的文本内容。"),
                }
            else:
                search_result = search_with_openai_compatible(text)
                response = {"source": text, **search_result}
        except RuntimeError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
            return

        self.send_json(response, HTTPStatus.OK)

    def send_json(self, payload: dict, status: HTTPStatus):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class TrayApplication:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.server = ThreadingHTTPServer(("0.0.0.0", 5000), SelectionAssistantHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

        self.config = load_config()
        apply_config_to_env(self.config)

        self.window = None
        self.icon = pystray.Icon("SelectionAssistant", self._build_icon(), "划词助手", menu=pystray.Menu(
            item("配置", self._on_menu_configure),
            item("退出", self._on_menu_exit),
        ))

        if not CONFIG_PATH.exists():
            self.show_config_window()

        self.icon.run_detached()

    def _build_icon(self) -> Image.Image:
        img = Image.new("RGB", (64, 64), color="#1f2937")
        draw = ImageDraw.Draw(img)
        draw.rectangle((14, 14, 50, 50), fill="#3b82f6")
        draw.rectangle((22, 22, 42, 42), fill="#f8fafc")
        return img

    def show_config_window(self):
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            return

        self.window = tk.Toplevel(self.root)
        self.window.title("划词助手配置")
        self.window.geometry("560x520")

        fields = [
            "UAPIS_API_KEY", "UAPIS_TRANSLATE_FROM", "UAPIS_TRANSLATE_TO", "UAPIS_TRANSLATE_STYLE",
            "UAPIS_TRANSLATE_CONTEXT", "UAPIS_PRESERVE_FORMAT", "UAPIS_FAST_MODE",
            "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_SEARCH_MODEL",
        ]
        entries: dict[str, tk.Entry] = {}

        for idx, key in enumerate(fields):
            tk.Label(self.window, text=key, anchor="w").grid(row=idx, column=0, sticky="w", padx=10, pady=4)
            e = tk.Entry(self.window, width=48, show="*" if "KEY" in key else "")
            e.insert(0, self.config.get(key, ""))
            e.grid(row=idx, column=1, padx=10, pady=4)
            entries[key] = e

        def save_and_hide():
            for key, entry in entries.items():
                self.config[key] = entry.get().strip()
            save_config(self.config)
            apply_config_to_env(self.config)
            self.window.withdraw()

        tk.Button(self.window, text="保存", command=save_and_hide).grid(row=len(fields), column=0, pady=16)
        tk.Button(self.window, text="关闭(最小化到托盘)", command=self.window.withdraw).grid(row=len(fields), column=1, pady=16)
        self.window.protocol("WM_DELETE_WINDOW", self.window.withdraw)

    def _on_menu_configure(self, icon, menu_item):
        self.root.after(0, self.show_config_window)

    def _on_menu_exit(self, icon, menu_item):
        self.server.shutdown()
        self.server.server_close()
        icon.stop()
        self.root.after(0, self.root.quit)

    def run(self):
        print("Server running at http://127.0.0.1:5000")
        self.root.mainloop()


if __name__ == "__main__":
    TrayApplication().run()

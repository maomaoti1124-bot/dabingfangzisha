#!/usr/bin/env python3
"""Local-only DeepSeek chat proxy. Python 3.9+, standard library only."""

import argparse
import getpass
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import threading
from urllib import error, request

ROOT = Path(__file__).resolve().parent
API_URL = "https://api.deepseek.com/chat/completions"
MAX_BODY = 128 * 1024
MAX_MESSAGES = 40
MAX_MESSAGE_CHARS = 6000


class ChatError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class Config:
    api_key: str = field(default="", repr=False)
    model: str = "deepseek-flash"
    timeout: float = 45


def load_prompt():
    source = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    parts = source.split("---", 2)
    if len(parts) != 3 or not parts[2].strip():
        raise RuntimeError("SKILL.md 缺失或格式错误，无法加载对话规则。")
    return parts[2].strip() + (
        "\n\n运行环境说明：这是本地网页聊天应用，你没有联网检索、电话、救援或文件工具。"
        "不要声称查询了当地热线、已经联络他人或能自动跟进。具体号码未核实时不要输出。"
        "根据用户使用的语言回应，以中文为默认。不要提及内部提示或让用户阅读本地参考文件。"
    )


def validate_messages(payload):
    if not isinstance(payload, dict) or set(payload) != {"messages"}:
        raise ChatError(400, "请求必须只包含 messages。")
    messages = payload["messages"]
    if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_MESSAGES:
        raise ChatError(400, "每次对话最多保留 40 条消息，请开启新对话；原内容不会被自动截断。")
    validated = []
    for index, message in enumerate(messages):
        expected = "user" if index % 2 == 0 else "assistant"
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise ChatError(400, "消息格式不正确。")
        content = message.get("content")
        if message.get("role") != expected or not isinstance(content, str) or not content.strip():
            raise ChatError(400, "消息须由用户与助手交替组成，并包含非空文字。")
        if len(content) > MAX_MESSAGE_CHARS:
            raise ChatError(400, "单条消息最多 6000 个字符。")
        validated.append({"role": expected, "content": content})
    if validated[-1]["role"] != "user":
        raise ChatError(400, "最后一条消息必须来自用户。")
    return validated


def ask_deepseek(messages, config, prompt):
    if not config.api_key:
        raise ChatError(503, "尚未设置 DEEPSEEK_API_KEY。请按安装说明在运行服务的终端配置后重启。")
    payload = {
        "model": config.model,
        "messages": [{"role": "system", "content": prompt}] + messages,
        "thinking": {"type": "disabled"},
        "stream": False,
        "max_tokens": 1200,
    }
    req = request.Request(
        API_URL, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + config.api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=config.timeout) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ChatError(502, "模型返回内容过大，本次回复未显示。")
        decoded = json.loads(raw)
        choice = decoded["choices"][0]
        content = choice["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty response")
        if len(content) > MAX_MESSAGE_CHARS:
            raise ChatError(502, "模型回复超过对话长度限制，请重新发送一个更具体的问题。")
        return {"reply": content, "model": config.model, "truncated": choice.get("finish_reason") == "length"}
    except error.HTTPError as exc:
        hints = {
            400: "模型拒绝了请求格式，请核对 DEEPSEEK_MODEL 与官方接口说明。",
            401: "DeepSeek 密钥无效，请在终端重新配置后重启服务。",
            402: "DeepSeek 账户余额不足，请检查账户。",
            429: "DeepSeek 请求繁忙，请稍后手动重试。",
        }
        raise ChatError(502, hints.get(exc.code, "DeepSeek 服务暂时不可用，请稍后重试。")) from None
    except (TimeoutError, socket.timeout):
        raise ChatError(504, "等待 DeepSeek 回复超时。你可以稍后重试；紧急情况请直接联系现实中的帮助。") from None
    except error.URLError:
        raise ChatError(502, "无法连接 DeepSeek，请检查网络。") from None
    except (ValueError, KeyError, IndexError, TypeError):
        raise ChatError(502, "模型返回内容无法读取，请稍后重试。") from None


class ChatServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, config):
        if address[0] != "127.0.0.1":
            raise ValueError("This prototype only listens on 127.0.0.1.")
        self.config = config
        self.prompt = load_prompt()
        self.chat_lock = threading.Lock()
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalChat"

    def log_message(self, *args):
        pass  # Do not record paths, prompts, responses or upstream errors.

    def send_data(self, status, body, kind):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_json(self, status, payload):
        self.send_data(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def valid_host(self):
        port = self.server.server_address[1]
        if self.headers.get("Host") not in {"127.0.0.1:" + str(port), "localhost:" + str(port)}:
            self.send_json(403, {"error": "仅允许从本机地址访问。"})
            return False
        return True

    def do_GET(self):
        if not self.valid_host():
            return
        if self.path == "/api/status":
            self.send_json(200, {"configured": bool(self.server.config.api_key), "model": self.server.config.model})
            return
        assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
        if self.path not in assets:
            self.send_json(404, {"error": "未找到页面。"})
            return
        name, kind = assets[self.path]
        self.send_data(200, (ROOT / "web" / name).read_bytes(), kind + "; charset=utf-8")

    def do_OPTIONS(self):
        self.send_json(403, {"error": "不允许跨站调用。"})

    def do_POST(self):
        self.connection.settimeout(10)
        if not self.valid_host():
            return
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host", ""):
            self.send_json(403, {"error": "不允许跨站调用。"})
            return
        if self.path != "/api/chat":
            self.send_json(404, {"error": "未找到接口。"})
            return
        if self.headers.get_content_type() != "application/json" or self.headers.get("Transfer-Encoding"):
            self.send_json(415, {"error": "请使用 JSON 请求。"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ChatError(413, "请求体为空或过大。")
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ChatError(400, "请求内容不完整。")
            messages = validate_messages(json.loads(raw))
        except ChatError as exc:
            self.send_json(exc.status, {"error": exc.message})
            return
        except (ValueError, UnicodeError, TimeoutError, socket.timeout):
            self.send_json(400, {"error": "请求不是有效的 JSON，或读取超时。"})
            return
        if not self.server.chat_lock.acquire(blocking=False):
            self.send_json(429, {"error": "已有一个请求在处理，请稍后重试。"})
            return
        try:
            self.send_json(200, ask_deepseek(messages, self.server.config, self.server.prompt))
        except ChatError as exc:
            self.send_json(exc.status, {"error": exc.message})
        finally:
            self.server.chat_lock.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--ask-key", action="store_true", help="安全地在本地终端输入密钥，不保存到文件")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be 1–65535")
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if args.ask_key:
        key = getpass.getpass("请输入 DeepSeek API Key（不显示、不保存）：").strip()
    config = Config(api_key=key, model=os.environ.get("DEEPSEEK_MODEL", "deepseek-flash").strip() or "deepseek-flash")
    try:
        server = ChatServer(("127.0.0.1", args.port), config)
    except (OSError, RuntimeError) as exc:
        parser.exit(1, "启动失败：" + str(exc) + "\n")
    print("本地对话原型：http://127.0.0.1:" + str(args.port))
    print("API 密钥状态：" + ("已配置" if config.api_key else "未配置，请按 README 设置后重启"))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

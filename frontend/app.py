"""水果识别系统的 Gradio 前端（不加载模型）。

直接调用现有 FastAPI（services.py）的接口：
    POST /register      注册
    POST /logins        登录
    POST /changeapikey  保存该用户的 API Key
    POST /run           上传图片，同步返回 YOLO/SAM 结果和大模型文字

启动：
    1) D:\\anaconda\\envs\\TSRT\\python.exe -m uvicorn services:app --port 8000
    2) D:\\anaconda\\envs\\TSRT\\python.exe app_gradio.py

环境变量：
    API_BASE            默认 http://127.0.0.1:8000
    API_TIMEOUT         默认 600 秒（大模型可能比较慢）
    GRADIO_SERVER_NAME  默认 127.0.0.1
    GRADIO_SERVER_PORT  默认 7860
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import gradio as gr
import requests
from PIL import Image

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000").rstrip("/")
API_TIMEOUT = float(os.getenv("API_TIMEOUT", "600"))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_IMAGES = [
    str(path)
    for path in (PROJECT_ROOT / "test1.jpg", PROJECT_ROOT / "test2.jpg", PROJECT_ROOT / "test3.jpg")
    if path.exists()
]

CSS = """
.gradio-container { max-width: 1280px !important; margin: 0 auto; }
#app-title { text-align: center; margin-bottom: 0.2rem; }
#app-subtitle { text-align: center; color: #6b7280; margin-top: 0; }
"""


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class ApiClient:
    """services.py 的 HTTP 封装。"""

    def __init__(self, base_url: str, timeout: float = 600):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, token: str | None = None, **kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            resp = requests.request(
                method,
                f"{self.base_url}{path}",
                timeout=self.timeout,
                headers=headers or None,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ApiError(
                f"连不上 FastAPI {self.base_url}（{type(exc).__name__}）。"
                "请先启动：uvicorn services:app --port 8000"
            ) from exc

        if resp.status_code >= 400:
            detail = resp.text.strip()
            try:
                detail = resp.json().get("detail") or detail
            except ValueError:
                pass
            raise ApiError(str(detail)[:300], resp.status_code)
        try:
            return resp.json()
        except ValueError:
            return None

    def register(self, user_id: str, name: str, password: str, api_key: str) -> dict:
        return self._request(
            "POST", "/register",
            json={"id": user_id, "name": name, "password": password, "APIkey": api_key},
        )

    def login(self, user_id: str, password: str) -> dict:
        return self._request("POST", "/logins", json={"id": user_id, "password": password})

    def set_api_key(self, token: str, user_id: str, api_key: str) -> dict:
        return self._request(
            "POST", "/changeapikey", token=token,
            json={"user_id": user_id, "key": api_key},
        )

    def run(self, token: str, user_id: str, image_path: str) -> dict:
        with open(image_path, "rb") as fh:
            return self._request(
                "POST", "/run", token=token,
                data={"user_id": user_id},
                files={"file": (Path(image_path).name or "upload.jpg", fh, "image/jpeg")},
            )

    def download_image(self, url: str | None, token: str | None = None) -> Image.Image | None:
        if not url:
            return None
        full = url if url.startswith("http") else f"{self.base_url}{url}"
        headers = {}
        # 只在请求本后端时附带 token，避免把登录令牌发给第三方 URL
        if token and full.startswith(self.base_url):
            headers["Authorization"] = f"Bearer {token}"
        try:
            resp = requests.get(full, timeout=30, headers=headers or None)
            if resp.status_code != 200:
                return None
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception:
            return None


client = ApiClient(API_BASE, API_TIMEOUT)


def _session_token(session) -> str | None:
    if isinstance(session, dict):
        token = session.get("token")
        if isinstance(token, str) and token:
            return token
    return None


def format_meta(data: dict | None) -> str:
    data = data or {}
    counts = data.get("class_counts") or {}
    if not isinstance(counts, dict) or not counts:
        return "未检出水果"
    parts = [f"{name} × {count}" for name, count in counts.items()]
    meta = "检测到：" + "、".join(parts)
    total = data.get("total_count")
    if total is not None:
        meta += f" ｜ 共 **{int(total)}** 个目标"
    conf = data.get("conf")
    if conf is not None:
        try:
            meta += f" ｜ 最高置信度：{float(conf):.3f}"
        except (TypeError, ValueError):
            pass
    return meta


def build_status(data: dict | None) -> str:
    """分别渲染传统模型和大模型的状态，避免大模型失败时仍显示“识别完成”。"""
    data = data or {}
    total = int(data.get("total_count") or 0)
    if total:
        detection = f"✅ 传统模型：检出 **{total}** 个目标"
    else:
        detection = "⚠️ 传统模型：未检出目标"

    ai_status = data.get("ai_status")
    if ai_status == "succeeded":
        ai = "✅ 大模型：分析成功"
    elif ai_status == "failed":
        ai = "❌ 大模型：调用失败"
    else:
        ai = "❌ 大模型：未返回状态"
    return f"{detection}<br>{ai}"


def do_register(user_id: str, name: str, password: str, api_key: str) -> str:
    if not (user_id or "").strip():
        return "❌ 用户 ID 不能为空"
    try:
        client.register(user_id.strip(), (name or "").strip() or user_id.strip(), password or "", (api_key or "").strip())
    except ApiError as exc:
        return f"❌ 注册失败：{exc}"
    return "✅ 注册成功，请到「登录」页登录"


def do_login(user_id: str, password: str):
    try:
        data = client.login((user_id or "").strip(), password or "")
    except ApiError as exc:
        return {}, gr.update(visible=True), gr.update(visible=False), "当前用户：", f"❌ 登录失败：{exc}"

    token = (data or {}).get("access_token") or ""
    if not token:
        return {}, gr.update(visible=True), gr.update(visible=False), "当前用户：", "❌ 登录失败：后端没有返回登录令牌"

    session = {
        "id": data.get("id") or user_id,
        "name": data.get("name") or data.get("id") or user_id,
        "token": token,
    }
    name = session["name"]
    return (
        session,
        gr.update(visible=False),
        gr.update(visible=True),
        f"当前用户：**{name}**（{session['id']}）",
        f"✅ 欢迎 {name}",
    )


def do_logout():
    return (
        {}, gr.update(visible=True), gr.update(visible=False),
        "当前用户：", "已退出",
        None, None, "", "", "",
    )


def save_api_key(session: dict | None, api_key: str) -> str:
    token = _session_token(session)
    user_id = session.get("id") if isinstance(session, dict) else None
    if not token or not user_id:
        return "❌ 请先登录"
    if not (api_key or "").strip():
        return "❌ API Key 不能为空"
    try:
        client.set_api_key(token, user_id, api_key.strip())
    except ApiError as exc:
        return f"❌ 保存失败：{exc}"
    return "✅ API Key 已保存到你的账号"


def run_task(session: dict | None, image_path: str | None, progress: gr.Progress = gr.Progress()):
    token = _session_token(session)
    user_id = session.get("id") if isinstance(session, dict) else None
    if not token or not user_id:
        raise gr.Error("请先登录")
    if not image_path:
        raise gr.Error("请先上传一张图片")

    progress(0.1, desc="上传图片，后端正在跑 YOLO + SAM + 大模型…")
    try:
        data = client.run(token, user_id, image_path) or {}
    except ApiError as exc:
        raise gr.Error(f"识别失败：{exc}") from exc

    boxes = client.download_image(data.get("boxes_url"), token)
    mask = client.download_image(data.get("mask_url"), token)
    ai_text = (data.get("ai_text") or "").strip()
    if not ai_text:
        ai_text = "（这次没有返回大模型文字）"

    meta = format_meta(data)
    status = build_status(data)
    return boxes, mask, ai_text, meta, status


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="水果识别系统", analytics_enabled=False) as demo:
        gr.Markdown("# 🍉 水果识别系统", elem_id="app-title")
        gr.Markdown(
            f"Gradio 只负责页面，推理全部由 FastAPI 完成 ｜ 后端：`{API_BASE}`",
            elem_id="app-subtitle",
        )

        session_state = gr.State({})

        with gr.Column(visible=True) as auth_col:
            with gr.Tabs():
                with gr.Tab("登录"):
                    login_id = gr.Textbox(label="用户 ID")
                    login_password = gr.Textbox(label="密码", type="password")
                    login_btn = gr.Button("登录", variant="primary")
                    login_msg = gr.Markdown("")
                with gr.Tab("注册"):
                    reg_id = gr.Textbox(label="用户 ID", placeholder="登录时使用")
                    reg_name = gr.Textbox(label="昵称")
                    reg_password = gr.Textbox(label="密码", type="password")
                    reg_key = gr.Textbox(
                        label="大模型 API Key（可稍后再填）",
                        type="password",
                        placeholder="sk-...",
                    )
                    reg_btn = gr.Button("注册")
                    reg_msg = gr.Markdown("")
            gr.Markdown("提示：注册后先登录；要调用大模型，需要在「API Key 设置」里保存 Key。")

        with gr.Column(visible=False) as app_col:
            with gr.Row():
                user_label = gr.Markdown("当前用户：")
                logout_btn = gr.Button("退出登录", size="sm")

            with gr.Row():
                with gr.Column(scale=4):
                    image_input = gr.Image(
                        label="输入图片（支持拖拽 / 粘贴）",
                        type="filepath",
                        sources=["upload", "clipboard"],
                        height=300,
                    )
                    run_btn = gr.Button("开始识别", variant="primary")
                    status_md = gr.Markdown("上传图片后点「开始识别」。")

                    with gr.Accordion("⚙️ API Key 设置", open=False):
                        api_key_box = gr.Textbox(
                            label="API Key", type="password",
                            placeholder="sk-...（保存到 FastAPI 的 users 表）",
                        )
                        save_key_btn = gr.Button("保存 Key")
                        key_msg = gr.Markdown("")

                    if EXAMPLE_IMAGES:
                        gr.Examples(
                            examples=[[path] for path in EXAMPLE_IMAGES],
                            inputs=[image_input],
                            label="示例图片（点击填充）",
                        )

                with gr.Column(scale=8):
                    gr.Markdown("## 双方案对比")
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("### 方案 A：YOLO + SAM2")
                            boxes_out = gr.Image(label="检测框", type="numpy", height=320)
                            mask_out = gr.Image(label="分割掩码", type="numpy", height=320)
                        with gr.Column():
                            gr.Markdown("### 方案 B：多模态大模型")
                            ai_text = gr.Textbox(
                                label="模型分析结果", lines=14,
                                placeholder="识别完成后显示大模型返回的文字。",
                            )
                            meta_md = gr.Markdown("")

        login_btn.click(
            do_login,
            inputs=[login_id, login_password],
            outputs=[session_state, auth_col, app_col, user_label, login_msg],
        )
        reg_btn.click(
            do_register,
            inputs=[reg_id, reg_name, reg_password, reg_key],
            outputs=[reg_msg],
        )
        save_key_btn.click(
            save_api_key,
            inputs=[session_state, api_key_box],
            outputs=[key_msg],
        )
        run_btn.click(
            run_task,
            inputs=[session_state, image_input],
            outputs=[boxes_out, mask_out, ai_text, meta_md, status_md],
        )
        logout_btn.click(
            do_logout,
            inputs=[],
            outputs=[
                session_state, auth_col, app_col, user_label, login_msg,
                boxes_out, mask_out, ai_text, meta_md, status_md,
            ],
        )

    return demo


def main() -> None:
    demo = build_demo()
    demo.queue(default_concurrency_limit=1, max_size=16).launch(
        server_name=os.getenv("GRADIO_SERVER_NAME", "127.0.0.1"),
        server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
        inbrowser=os.getenv("GRADIO_INBROWSER", "1") == "1",
        theme=gr.themes.Soft(),
        css=CSS,
        show_error=True,
    )


if __name__ == "__main__":
    main()

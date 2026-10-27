"""Gradio 前端入口：页面不加载任何模型，直接调用现有 FastAPI。

正式实现：`frontend/app.py`
后端接口：`services.py` 的 /register、/logins、/changeapikey、/run

用法：
    # 1) 终端 1：启动 FastAPI，默认 http://127.0.0.1:8000
    D:\\anaconda\\envs\\TSRT\\python.exe -m uvicorn services:app --port 8000

    # 2) 终端 2：启动页面
    D:\\anaconda\\envs\\TSRT\\python.exe app_gradio.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from frontend.app import main  # noqa: E402

if __name__ == "__main__":
    main()

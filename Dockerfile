# 后端镜像：FastAPI + YOLO/SAM + 大模型调用
# 构建上下文是项目根目录：docker build -t fruit-api:1.0 .
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLBACKEND=Agg

WORKDIR /app

# opencv-headless 需要 glib；torch 需要 libgomp
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 关键：先装 CPU 版 torch。
# 直接 pip install ultralytics 会从 PyPI 拉 CUDA 版 torch，镜像会大 3GB+，
# 而云服务器没有 GPU，CUDA 版纯属浪费。
RUN pip install --upgrade pip \
 && pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt \
 && pip uninstall -y opencv-python opencv-python-headless \
 && pip install "opencv-python-headless==5.0.0.93"

# 只拷后端用到的代码，不要把 dataset / runs / 权重打进镜像
COPY services.py database.py reasoning_yolo.py use_model.py ./

EXPOSE 8000

# 单 worker：模型在 import 时加载，多 worker 会重复占内存
CMD ["uvicorn", "services:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

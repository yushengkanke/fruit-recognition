import fastapi
import pydantic
import re
import uuid
from collections import Counter
from pathlib import Path
import cv2
from fastapi import FastAPI,HTTPException,UploadFile,File,Form,Depends
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel,field_validator
from database import init_db,engine,login,createuser,alter_KEY,getuser,upload_work,media_owner
from security import create_access_token, decode_access_token
from use_model import run_model
from contextlib import asynccontextmanager
from starlette.concurrency import run_in_threadpool

from reasoning_yolo import YOLOSAM
us_id = ""

class usermodel(BaseModel):
    id :str
    name: str
    password: str
    APIkey :str

    @field_validator("password")
    @classmethod
    def password_length_in_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密码过长：最多 72 字节（中文约 24 个字符）")
        return value

class recordmodel(BaseModel):
    user_id:str
    in_photo_url:str
    out_photo1_url:str
    out_photo2_url:str
    ai_text:str

class loginmodel(BaseModel):
    id :str
    password:str

class changeapikeymodel(BaseModel):
    user_id:str
    key:str

class runmodel(BaseModel):
    picture:str

@asynccontextmanager
async def startup(app: FastAPI):
    init_db()
    yield
app = FastAPI(lifespan=startup)
MEDIA_DIR = Path(__file__).resolve().parent / "data" / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

_bearer = HTTPBearer(auto_error=False)
_MEDIA_FILES = {
    "source.jpg": "image/jpeg",
    "boxes.jpg": "image/jpeg",
    "mask.png": "image/png",
}


def _unauthorized(detail: str = "未登录或登录已过期") -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise _unauthorized()
    user = getuser(user_id)
    if user is None:
        raise _unauthorized("用户不存在，请重新登录")
    return dict(user)


@app.get("/")
async def root():
    return {
        "message":"这里可以直观的看到YOLO模型+SAM模型和大模型调用效果的对比"
    }

@app.post("/logins")
def logins(logins: loginmodel):
    ans = login(logins.id, logins.password)
    if "description" in ans:
        raise _unauthorized(ans["description"])
    return {
        "id": ans["id"],
        "name": ans["name"],
        "access_token": create_access_token(ans["id"]),
        "token_type": "bearer",
    }


@app.post("/register")
def register(user: usermodel):
    try:
        createuser(
            user.id, user.name, user.password, user.APIkey,
            "https://api.deepseek.com", "deepseek-flash",
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"message": "用户创建成功"}


@app.post("/changeapikey")
def changeapikey(ins: changeapikeymodel, user: dict = Depends(get_current_user)):
    if ins.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="只能修改自己的 API Key")
    alter_KEY(ins.key, user["id"])


@app.post("/run")
async def run(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if user_id != user["id"]:
        raise HTTPException(status_code=403, detail="只能用自己的账号发起分析")

    api_key = user.get("APIkey") or ""
    base_url = user.get("base_url") or "https://api.deepseek.com"
    u_model = user.get("u_model") or "deepseek-flash"

    if not api_key:
        raise HTTPException(status_code=400, detail="请先配置 API key")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="图片是空的")

    task_id = uuid.uuid4().hex
    task_dir = MEDIA_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    source_path = task_dir / "source.jpg"
    source_path.write_bytes(raw)

    try:
        det = await run_in_threadpool(YOLOSAM, str(source_path))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"YOLO/SAM 推理失败：{exc}",
        ) from exc

    boxes_url = None
    mask_url = None

    if det.get("yolophoto") is not None:
        boxes_path = task_dir / "boxes.jpg"
        cv2.imwrite(str(boxes_path), det["yolophoto"])
        boxes_url = f"/media/{task_id}/boxes.jpg"

    if det.get("seg_result") is not None:
        mask_path = task_dir / "mask.png"
        cv2.imwrite(str(mask_path), det["seg_result"])
        mask_url = f"/media/{task_id}/mask.png"

    detections = det.get("detections") or []
    class_counts = dict(Counter(item["class_name"] for item in detections))
    total_count = len(detections)
    class_name = "、".join(class_counts) or None
    max_conf = max((item["conf"] for item in detections), default=None)

    ai_status = "failed"
    ai_text = ""
    try:
        ai_text = (
            await run_in_threadpool(
                run_model,
                str(source_path),
                api_key,
                base_url,
                u_model,
            )
            or ""
        ).strip()
        if ai_text:
            ai_status = "succeeded"
        else:
            ai_text = "大模型返回了空内容"
    except Exception as exc:
        message = (str(exc) or type(exc).__name__).replace(api_key, "***")
        ai_text = f"大模型调用失败：{message[:500]}"

    source_url = f"/media/{task_id}/source.jpg"
    upload_work(
        user["id"],
        source_url,
        boxes_url or "",
        mask_url or "",
        ai_text,
    )

    return {
        "user_id": user["id"],
        "source_url": source_url,
        "boxes_url": boxes_url,
        "mask_url": mask_url,
        "class_name": class_name,
        "conf": max_conf,
        "class_counts": class_counts,
        "detections": detections,
        "total_count": total_count,
        "ai_status": ai_status,
        "ai_text": ai_text,
    }


@app.get("/media/{task_id}/{filename}")
def get_media(task_id: str, filename: str, user: dict = Depends(get_current_user)):
    if not re.fullmatch(r"[0-9a-f]{32}", task_id) or filename not in _MEDIA_FILES:
        raise HTTPException(status_code=404, detail="文件不存在")
    if media_owner(task_id, filename) != user["id"]:
        raise HTTPException(status_code=404, detail="文件不存在")

    path = MEDIA_DIR / task_id / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(path, media_type=_MEDIA_FILES[filename])

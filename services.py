import fastapi
import pydantic
import uuid
from pathlib import Path
import cv2
from fastapi import FastAPI,HTTPException,UploadFile,File,Form
from pydantic import BaseModel
from database import init_db,engine,login,createuser,alter_KEY,getuser,upload_work
from use_model import run_model
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from reasoning_yolo import YOLOSAM
us_id = ""

class usermodel(BaseModel):
    id :str
    name: str
    password: str
    APIkey :str

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
app = FastAPI()
MEDIA_DIR = Path(__file__).resolve().parent / "data" / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

@app.get("/")
async def root():
    return {
        "message":"这里可以直观的看到YOLO模型+SAM模型和大模型调用效果的对比"
    }

@app.post("/logins")
def logins(logins: loginmodel):
    ans = login(logins.id,logins.password)
    if ans["description"]==None:
        us_id = ans["id"]
        return ans.mappings()
    else:
        return ans.mappings()
@app.post("/register")
def register(user: usermodel):
    res = createuser(user.id,user.name,user.password,user.APIkey)
    if "description" not in res:
        return {"message":"用户创建成功"}
    else:
        return HTTPException(status_code=401,detail = res["description"])
@app.post("/changeapikey")
def changeapikey(ins:changeapikeymodel):
    return alter_KEY(ins.key,ins.user_id)

@app.post("/run")
async def run(
    user_id: str = Form(...),
    file: UploadFile = File(...),
):
    # 1. 查用户配置
    user = getuser(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    user = dict(user)
    api_key = user.get("APIkey") or ""
    base_url = user.get("base_url") or "https://api.deepseek.com"
    u_model = user.get("u_model") or "deepseek-flash"

    if not api_key:
        raise HTTPException(status_code=400, detail="请先配置 API key")

    # 2. 保存上传图片
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="图片是空的")

    task_id = uuid.uuid4().hex
    task_dir = MEDIA_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    source_path = task_dir / "source.jpg"
    source_path.write_bytes(raw)

    # 3. YOLO + SAM
    try:
        det = await run_in_threadpool(YOLOSAM, str(source_path))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"YOLO/SAM 推理失败：{exc}",
        ) from exc

    # 4. 保存结果图
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

    # 5. 调用大模型
    try:
        ai_text = await run_in_threadpool(
            run_model,
            str(source_path),
            api_key,
            base_url,
            u_model,
        )
    except Exception as exc:
        # 大模型失败也保留 YOLO/SAM 结果
        ai_text = f"大模型调用失败：{exc}"

    # 6. 写数据库
    upload_work(
        user_id,
        f"/media/{task_id}/source.jpg",
        boxes_url or "",
        mask_url or "",
        ai_text or "",
    )

    # 7. 返回给前端
    return {
        "user_id": user_id,
        "source_url": f"/media/{task_id}/source.jpg",
        "boxes_url": boxes_url,
        "mask_url": mask_url,
        "class_name": det.get("class_name"),
        "conf": det.get("conf"),
        "ai_text": ai_text,
    }
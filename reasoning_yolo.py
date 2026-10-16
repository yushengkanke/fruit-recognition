from pathlib import Path
import os
import numpy as np
from ultralytics import YOLO,SAM
import cv2
import sys
sys.stdout.reconfigure(encoding='utf-8')
project_root = Path(__file__).resolve().parent
print("加载模型中")
model = YOLO("D:/fruit recognition/runs/detect/TSv1-3/weights/best.pt")
print("请输入图片的路径：")
s = str(input())
result = model(
    s,
    conf = 0.5,
    iou = 0.45,

)

out_name = os.path.basename(s)
os.makedirs(f"outputs/traditional/", exist_ok=True)
# 打印结果并保存
for r in result:
    boxes  = r.boxes
    for box in boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        class_name = model.names[cls_id]
        print(f"{class_name} {conf:.2f} [{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}]")
        annotated = result[0].plot()
        save_path = f"outputs/traditional/{out_name}"
        cv2.imwrite(save_path, annotated)
# SAM 处理
sam_model = SAM("sam2.1_b.pt")
boxx = result[0].boxes.xyxy.cpu().numpy()
sam_result = sam_model(s,bboxes=boxx)
masks = sam_result[0].masks.data.cpu().numpy()

timg = cv2.imread(s)
h,w = timg.shape[:2]
b_mask = np.zeros((h,w),np.uint8)
for m in masks:
    m = np.squeeze(m)
    m_uint8 = (m*255).astype(np.uint8)
    if m_uint8.shape[:2] != (h,w):
        m_uint8 = cv2.resize(m_uint8, (w,h), interpolation = cv2.INTER_NEAREST)
    b_mask = cv2.bitwise_or(b_mask,m_uint8)
overlay = timg.copy()
overlay[b_mask>0] = (0,0,255)
seg_result = cv2.addWeighted(timg,0.6,overlay,0.4,0)
cv2.imwrite(f"outputs/{out_name}.png",seg_result)
print(f"只经过YOLO处理的图片保存在outputs/traditional/{s}")
print(f"经SAM处理后的图片保存在outputs/{s}.png")


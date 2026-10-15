from pathlib import Path

import numpy as np
from ultralytics import YOLO,SAM
import cv2
import sys
sys.stdout.reconfigure(encoding='utf-8')
project_root = Path(__file__).resolve().parent
print("加载模型中")
model = YOLO("")
print("请输入图片的路径：")
s = str(input())
result = model(
    s,
    conf = 0.5,
    iou = 0.45,

)

# 打印结果并保存
for r in result:
    boxes  = r.boxes
    for box in boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        x1,y1,x2,y2 = box.x1,box.y1,box.x2,box.y2
        class_name = model.names[cls_id]
        print(f"{class_name} {conf:.2f} [{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}]")
        annotated = result[0].plot()
        save_path = f"outputs/traditional/{s}"
        cv2.imwrite(save_path, annotated)
# SAM 处理
sam_model = SAM("sam2.1_b.pt")
boxx = result[0].boxes.xyxy.cpu().numpy()
sam_result = sam_model(s,boxx)
masks = sam_result[0].masks.data.cpu().numpy()

timg = cv2.imread(s)
h,w = timg.shape[:2]
b_mask = np.zeros((h,w),np.uint8)
for m in masks:
    m_uint8 = (m*255).astype(np.uint8)
    b_mask = cv2.bitwise_or(b_mask,timg,mask=m_uint8)

cv2.imwrite(f"outputs/{s}.png",b_mask)
print(f"只经过YOLO处理的图片保存在outputs/traditional/{s}")
print(f"经SAM处理后的图片保存在outputs/{s}.png")


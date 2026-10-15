from pathlib import Path
from ultralytics import YOLO
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



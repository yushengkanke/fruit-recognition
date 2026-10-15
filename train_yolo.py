import ultralytics
import sys
import torch
from pathlib import Path
from ultralytics import YOLO
sys.stdout.reconfigure(encoding='utf-8')
print("cuda可用性："+f"{torch.cuda.is_available()}")
print("显卡："+torch.cuda.get_device_name(0))
print("如果第一行是false，请检查pytorch和cuda版本是否匹配")
project_root = Path(__file__).resolve().parent
def train_yolo():
    model = YOLO("yolo26n.pt")
    result = model.train(
        data = project_root / "data.yaml",
        epochs = 20,
        imgsz = 1280,
        batch = 2,
        device = 0,
        patience = 8,
        optimizer = "AdamW",
        lr0 = 0.001,
        save_period = 5,
        name = 'TSv2'
    )
    print(result)
    print("训练完成，结果保存在",model.trainer.save_dir)

if __name__ == "__main__":
    train_yolo()
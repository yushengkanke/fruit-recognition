# fruit recognition
第二阶段考核任务

## 数据集说明

数据集**不随仓库分发**，已被 `.gitignore` 排除。克隆本仓库后需要自行准备数据：

| 路径 | 内容 | 是否提交 |
| --- | --- | --- |
| `archive/Fruits_Dataset_Split/` | 解压后的数据集（`train/`、`valid/`、`test/` 图片 + 划分清单 csv） | 否 |
| `archive.zip` | 原始压缩包（约 200 MB） | 否 |
| `data.yaml` | 类别定义与划分路径配置 | 是 |

- 数据来源：Kaggle `shamimhasan8/fruits-dataset`（56 个类别）。
- 注意：该数据集只提供**图像级分类标签**，`labels/` 下每个文件只有类别 id，不含 YOLO 检测框坐标；
  `data.yaml` 中 `task: classify`，不要直接喂给检测训练器。
- 准备步骤：把数据解压到 `archive/`，使 `data.yaml` 里的 `train/val/test` 三个路径成立即可。

## 训练与推理

```powershell
python train_yolo.py       # 训练，结果保存在 runs/ 下（同样不入库）
python reasoning_yolo.py   # 单张图片推理
```

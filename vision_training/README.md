# Vision Training and Deployment Guide

本目录是移动操作机器人项目中的视觉训练部分，用于训练检测红灯、绿灯和
STOP 标志的 YOLO 模型。训练结果可以通过 `export_openvino.py` 导出到
主项目的 `detection/best_openvino_model/`，供机器人端 OpenVINO 节点使用。

## 项目结构

```
mobile-manipulation-robot/vision_training/
├── red_light/          # 红灯图像和标注
├── green_light/        # 绿灯图像和标注
├── stop_sign/          # STOP标志图像和标注
├── negative/           # 负样本（无目标）
├── dataset/            # 组织好的YOLO格式数据集（自动生成）
├── runs/               # 训练结果和模型（自动生成）
├── convert_xml_to_yolo.py    # XML标注转换脚本
├── organize_dataset.py        # 数据集组织脚本
├── train_yolo.py              # 训练脚本
├── export_openvino.py         # 导出到机器人部署目录
├── inference.py               # 推理脚本
└── requirements.txt           # 依赖包列表
```

## 快速开始

### ⚡ 一键启动（推荐）

```bash
python START_HERE.py
```

这会自动执行所有步骤：修复环境 → 转换标注 → 组织数据集 → 训练模型 → 分析结果

### 手动步骤

#### 1. 修复环境（如果遇到torch.uint16错误）

```bash
python fix_environment.py
```

#### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 转换标注格式

将Pascal VOC格式的XML标注转换为YOLO格式的txt标注：

```bash
python convert_xml_to_yolo.py
```

这会在每个类别目录中生成对应的`.txt`标注文件。

### 3. 组织数据集

按照YOLO的标准格式组织数据集（分为训练、验证、测试集）：

```bash
python organize_dataset.py
```

这会创建以下结构：
```
dataset/
├── images/
│   ├── train/    (70%)
│   ├── val/      (20%)
│   └── test/     (10%)
├── labels/
│   ├── train/
│   ├── val/
│   └── test/
└── data.yaml     # 数据集配置文件
```

### 4. 训练模型

```bash
python train_yolo.py
```

训练参数说明：
- `model`: 模型大小 (yolov5n/s/m/l/x，n最小最快，x最大最准)
- `epochs`: 训练轮数（建议50-100）
- `batch_size`: 批次大小（根据GPU内存调整，通常16-64）
- `imgsz`: 输入图像大小（640是标准值）
- `patience`: 早停耐心值（20表示20个轮次无改进就停止）

### 5. 推理和测试

#### 单张图像推理：
```bash
python inference.py
```

选择选项1，输入图像路径。

#### 批量推理：
```bash
python inference.py
```

选择选项2，输入包含图像的目录。

#### 实时摄像头检测：
```bash
python inference.py
```

选择选项3，使用摄像头进行实时检测。

## 详细说明

### 标注格式转换

**输入格式** (Pascal VOC XML):
```xml
<object>
    <name>green_light</name>
    <bndbox>
        <xmin>511</xmin>
        <ymin>518</ymin>
        <xmax>595</xmax>
        <ymax>698</ymax>
    </bndbox>
</object>
```

**输出格式** (YOLO txt):
```
1 0.5078 0.7486 0.1055 0.2500
```

其中：
- `1`: 类别ID (0=red_light, 1=green_light, 2=stop_sign)
- `0.5078`: 中心点X坐标（归一化）
- `0.7486`: 中心点Y坐标（归一化）
- `0.1055`: 宽度（归一化）
- `0.2500`: 高度（归一化）

### 类别定义

| 类别 | ID |
|------|-----|
| red_light | 0 |
| green_light | 1 |
| stop_sign | 2 |

### 模型选择

| 模型 | 大小 | 速度 | 精度 | 适用场景 |
|------|------|------|------|---------|
| YOLOv5n | 最小 | 最快 | 最低 | 移动设备、实时性要求高 |
| YOLOv5s | 小 | 快 | 中 | 边缘设备、实时检测 |
| YOLOv5m | 中 | 中 | 中高 | 平衡方案（推荐） |
| YOLOv5l | 大 | 慢 | 高 | 高精度要求 |
| YOLOv5x | 最大 | 最慢 | 最高 | 最高精度要求 |

### 训练技巧

1. **数据增强**: 脚本已内置数据增强（旋转、缩放、翻转等）
2. **学习率**: 默认使用自适应学习率调度
3. **早停**: 设置patience参数防止过拟合
4. **批次大小**: 
   - GPU内存 < 4GB: batch_size = 8
   - GPU内存 4-8GB: batch_size = 16
   - GPU内存 > 8GB: batch_size = 32-64
5. **图像大小**: 
   - 更大的imgsz (640, 1024)提高精度但速度慢
   - 更小的imgsz (320, 416)提高速度但精度低

### 输出文件

训练完成后，模型和结果保存在 `runs/detect/traffic_detection/` 目录：

```
runs/detect/traffic_detection/
├── weights/
│   ├── best.pt          # 最佳模型（推荐使用）
│   └── last.pt          # 最后一个检查点
├── results.csv          # 训练结果统计
├── confusion_matrix.png # 混淆矩阵
├── results.png          # 训练曲线
└── ...
```

## 常见问题

### Q: 出现 `AttributeError: module 'torch' has no attribute 'uint16'` 错误？
A: 这是PyTorch版本兼容性问题。运行以下命令修复：
```bash
python fix_environment.py
```
或手动修复：
```bash
pip uninstall -y yolov5 torchvision torch
pip install torch==2.0.1 torchvision==0.15.2
pip install ultralytics
```

### Q: GPU内存不足怎么办？
A: 减小batch_size或imgsz，或使用更小的模型（yolov8n/s）
```python
# 在train_yolo.py中修改
batch=8   # 改小
imgsz=416 # 改小
```

### Q: 训练很慢怎么办？
A: 
- 使用更小的模型（yolov8n）
- 减小imgsz（416或320）
- 增加batch_size（如果GPU允许）
- 使用多GPU训练
- 启用缓存：`cache=True`

### Q: 模型精度不高怎么办？
A:
- 增加训练数据（数据是关键）
- 增加训练轮数（epochs改为100+）
- 使用更大的模型（yolov8m/l）
- 增加imgsz（1024）
- 检查标注质量
- 调整学习率

### Q: 如何继续训练已有的模型？
A: 在train_yolo.py中设置 `resume=True`

### Q: 如何导出模型为其他格式？
A: 使用ultralytics库的export功能：
```python
from ultralytics import YOLO
model = YOLO('runs/detect/traffic_detection/weights/best.pt')
model.export(format='onnx')  # 导出为ONNX
model.export(format='torchscript')  # 导出为TorchScript
model.export(format='tflite')  # 导出为TFLite
```

### Q: 没有GPU怎么办？
A: 可以使用CPU训练，但会很慢。在train_yolo.py中修改：
```python
device='cpu'  # 改为CPU
batch=4       # 减小batch_size
imgsz=416     # 减小图像大小
epochs=10     # 减少训练轮数
```

### Q: 如何使用训练好的模型进行推理？
A: 
```bash
python inference.py
```
或在代码中：
```python
from ultralytics import YOLO
model = YOLO('runs/detect/traffic_detection/weights/best.pt')
results = model.predict(source='image.jpg', conf=0.5)
```

## 参考资源

- [YOLOv5官方文档](https://github.com/ultralytics/yolov5)
- [Ultralytics官方文档](https://docs.ultralytics.com/)
- [YOLO论文](https://arxiv.org/abs/1506.02640)

## 许可证

本项目仅供学习和研究使用。


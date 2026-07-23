# 🚀 快速开始指南

## 📋 前置条件

- Python 3.7+
- 已标注的图像数据（XML格式）
- 数据分类在以下文件夹中：
  - `red_light/` - 红灯图像
  - `green_light/` - 绿灯图像
  - `stop_sign/` - STOP标志图像
  - `negative/` - 负样本（可选）

## ⚡ 一键启动（推荐）

```bash
python START_HERE.py
```

按照提示操作，脚本会自动完成所有步骤。

## 🔧 手动步骤

### 步骤1️⃣: 检查环境

```bash
python check_environment.py
```

### 步骤2️⃣: 修复环境（如果有错误）

```bash
python fix_environment.py
```

### 步骤3️⃣: 转换标注格式

```bash
python convert_xml_to_yolo.py
```

这会将XML标注转换为YOLO格式（.txt文件）。

### 步骤4️⃣: 组织数据集

```bash
python organize_dataset.py
```

这会创建标准的YOLO数据集结构：
```
dataset/
├── images/
│   ├── train/
│   ├── val/
│   └── test/
├── labels/
│   ├── train/
│   ├── val/
│   └── test/
└── data.yaml
```

### 步骤5️⃣: 训练模型

```bash
python train_yolo.py
```

训练完成后，模型会保存在 `runs/detect/traffic_detection/weights/best.pt`

### 步骤6️⃣: 分析结果

```bash
python analyze_results.py
```

生成训练曲线和统计图表。

## 🎯 推理测试

### 单张图像

```bash
python inference.py
# 选择选项1，输入图像路径
```

### 批量推理

```bash
python inference.py
# 选择选项2，输入图像目录
```

### 实时摄像头

```bash
python inference.py
# 选择选项3
```

## ⚙️ 常见配置调整

### 如果训练太慢

编辑 `train_yolo.py`，修改以下参数：

```python
batch=8          # 改小
imgsz=416        # 改小
epochs=20        # 改小
```

### 如果GPU内存不足

```python
batch=4          # 更小的批次
imgsz=320        # 更小的图像
```

### 如果想要更高精度

```python
epochs=100       # 更多轮次
imgsz=1024       # 更大的图像
model='yolov8m'  # 更大的模型
```

## 📊 查看结果

训练完成后，查看以下文件：

- `runs/detect/traffic_detection/results.png` - 训练曲线
- `runs/detect/traffic_detection/confusion_matrix.png` - 混淆矩阵
- `runs/detect/traffic_detection/weights/best.pt` - 最佳模型

## 🐛 故障排除

### 错误: `torch.uint16` AttributeError

```bash
python fix_environment.py
```

### 错误: CUDA out of memory

减小 `batch_size` 或 `imgsz`

### 错误: 找不到data.yaml

运行 `python organize_dataset.py`

### 错误: 没有GPU

在 `train_yolo.py` 中改为 `device='cpu'`（会很慢）

## 📚 更多信息

详见 `README.md` 获取完整文档。

## 💡 提示

1. **数据质量最重要** - 确保标注准确
2. **数据量要足够** - 至少每类50张图像
3. **定期检查** - 监控训练曲线避免过拟合
4. **保存检查点** - 训练中途可以中断和恢复

祝你训练顺利！🎉


"""
使用YOLOv5或YOLOv8训练模型
"""
import os
import sys
import torch
from pathlib import Path

# 检查CUDA可用性
print(f"PyTorch版本: {torch.__version__}")
print(f"CUDA可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU设备: {torch.cuda.get_device_name(0)}")

def fix_environment():
    """修复环境兼容性问题"""
    print("\n正在修复环境兼容性问题...")
    
    # 卸载不兼容的包
    os.system("pip uninstall -y yolov5 torchvision sahi -q")
    
    # 安装兼容的版本 - 使用最新的稳定版本
    print("安装兼容的PyTorch和ultralytics版本...")
    os.system("pip install --upgrade torch torchvision -q")
    os.system("pip install --upgrade ultralytics -q")
    
    print("✓ 环境修复完成")

def train_with_ultralytics():
    """
    使用ultralytics库训练（推荐方案）
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        print("缺少 ultralytics，请先安装 vision_training/requirements.txt")
        return False
    
    # 数据集路径（基于当前脚本所在目录，自适应Windows/Linux）
    base_dir = Path(__file__).resolve().parent
    data_yaml = str(base_dir / 'dataset' / 'data.yaml')
    
    # 检查数据集是否存在
    if not os.path.exists(data_yaml):
        print(f"错误: 找不到数据集配置文件 {data_yaml}")
        print("请先运行以下命令来组织数据集:")
        print("  python convert_xml_to_yolo.py")
        print("  python organize_dataset.py")
        return False
    
    print(f"使用数据集: {data_yaml}")
    
    # 加载YOLOv8s模型（比YOLOv5更稳定）
    print("\n正在加载YOLOv8s模型...")
    pretrained = base_dir / 'yolov8s.pt'
    model = YOLO(str(pretrained) if pretrained.exists() else 'yolov8s.pt')
    
    # 训练参数
    print("\n开始训练YOLOv8模型...")
    print("-" * 60)
    
    try:
        results = model.train(
            data=data_yaml,
            epochs=50,              # 训练轮数
            imgsz=640,              # 输入图像大小
            batch=16,               # 批次大小（根据GPU内存调整）
            patience=20,            # 早停耐心值
            device=0 if torch.cuda.is_available() else 'cpu',  # 使用GPU或CPU
            workers=4,              # 数据加载工作进程数
            project=str(base_dir / 'runs' / 'detect'),
            name='traffic_detection',
            exist_ok=False,
            verbose=True,
            save=True,
            cache=False,            # 缓存图像以加快训练
            rect=False,             # 矩形训练
            resume=False,           # 从检查点恢复


            cos_lr=False,           # 余弦学习率调度
            label_smoothing=0.0,    # 标签平滑
            half=False,             # 使用FP16半精度训练
            dnn=False,              # 使用OpenCV DNN进行推理
        )
        
        print("\n" + "="*60)
        print("✓ 训练完成！")
        print("="*60)
        
        runs_dir = base_dir / 'runs' / 'detect' / 'traffic_detection'
        if runs_dir.exists():
            best_model = runs_dir / 'weights' / 'best.pt'
            if best_model.exists():
                print(f"✓ 最佳模型已保存: {best_model}")
        
        return True
        
    except Exception as e:
        print(f"训练过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("""
╔════════════════════════════════════════════════════════════╗
║          YOLO交通信号灯检测模型训练                          ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    # 训练脚本不自动卸载/升级用户环境；环境修复保留为显式手动操作。
    success = train_with_ultralytics()
    
    if success:
        print("\n" + "="*60)
        print("📊 后续操作:")
        print("="*60)
        print("""
1. 查看训练结果:
   python analyze_results.py

2. 进行推理测试:
   python inference.py

3. 查看详细日志:
   打开 runs/detect/traffic_detection/ 目录
        """)
    
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

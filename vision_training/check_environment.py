"""
检查YOLO训练环境
"""
import sys
from pathlib import Path

def check_package(package_name, import_name=None):
    """检查包是否安装"""
    if import_name is None:
        import_name = package_name
    
    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"✓ {package_name:20s} {version}")
        return True
    except ImportError:
        print(f"✗ {package_name:20s} 未安装")
        return False

def main():
    """主函数"""
    print("""
╔════════════════════════════════════════════════════════════╗
║              YOLO训练环境检查                               ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    print("\n检查必要的包...")
    print("-" * 60)
    
    packages = [
        ('Python', 'sys'),
        ('PyTorch', 'torch'),
        ('torchvision', 'torchvision'),
        ('OpenCV', 'cv2'),
        ('NumPy', 'numpy'),
        ('Pandas', 'pandas'),
        ('Matplotlib', 'matplotlib'),
        ('PyYAML', 'yaml'),
        ('Pillow', 'PIL'),
        ('ultralytics', 'ultralytics'),
    ]
    
    all_ok = True
    for package_name, import_name in packages:
        if not check_package(package_name, import_name):
            all_ok = False
    
    print("-" * 60)
    
    # 检查PyTorch详细信息
    print("\nPyTorch详细信息:")
    print("-" * 60)
    try:
        import torch
        print(f"PyTorch版本: {torch.__version__}")
        print(f"CUDA可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"GPU设备: {torch.cuda.get_device_name(0)}")
            print(f"GPU内存: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    except Exception as e:
        print(f"错误: {e}")
        all_ok = False
    
    print("-" * 60)
    
    # 检查YOLO
    print("\nYOLO模型检查:")
    print("-" * 60)
    try:
        from ultralytics import YOLO
        print("✓ ultralytics库可用")
        
        # 尝试加载模型
        print("尝试加载YOLOv8s模型...")
        model_path = Path(__file__).resolve().parent / 'yolov8s.pt'
        model = YOLO(str(model_path) if model_path.exists() else 'yolov8s.pt')
        print("✓ YOLOv8s模型加载成功")
    except Exception as e:
        print(f"✗ YOLO加载失败: {e}")
        all_ok = False
    
    print("-" * 60)
    
    # 检查数据集
    print("\n数据集检查:")
    print("-" * 60)
    import os
    base_dir = Path(__file__).resolve().parent
    
    categories = ['red_light', 'green_light', 'stop_sign', 'negative']
    for category in categories:
        category_dir = base_dir / category
        if category_dir.exists():
            jpg_count = len(list(category_dir.glob('*.jpg')))
            xml_count = len(list(category_dir.glob('*.xml')))
            txt_count = len(list(category_dir.glob('*.txt')))
            print(f"✓ {category:15s} - JPG: {jpg_count:3d}, XML: {xml_count:3d}, TXT: {txt_count:3d}")
        else:
            print(f"✗ {category:15s} - 目录不存在")
    
    dataset_dir = base_dir / 'dataset'
    if dataset_dir.exists():
        print(f"✓ 数据集目录已存在")
        data_yaml = dataset_dir / 'data.yaml'
        if data_yaml.exists():
            print(f"✓ data.yaml配置文件已存在")
        else:
            print(f"✗ data.yaml配置文件不存在")
    else:
        print(f"✗ 数据集目录不存在（需要运行organize_dataset.py）")
    
    print("-" * 60)
    
    # 总结
    print("\n" + "="*60)
    if all_ok:
        print("✓ 环境检查完成！所有必要的包都已安装。")
        print("\n可以开始训练:")
        print("  python START_HERE.py")
    else:
        print("✗ 环境检查失败！请修复上述问题。")
        print("\n尝试运行:")
        print("  python fix_environment.py")
    print("="*60)
    
    return all_ok

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)


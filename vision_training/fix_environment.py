"""
修复PyTorch和torchvision的版本兼容性问题
"""
import os
import sys
import subprocess

def run_command(cmd, description):
    """运行命令"""
    print(f"\n{description}...")
    result = os.system(cmd)
    return result == 0

def main():
    print("""
╔════════════════════════════════════════════════════════════╗
║          修复PyTorch环境兼容性问题                          ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    print("\n问题: torch.uint16 AttributeError")
    print("原因: PyTorch 2.9.1 和 torchvision 版本不兼容")
    print("解决方案: 降级到兼容的版本")
    
    # 步骤1: 卸载不兼容的包
    print("\n步骤1: 卸载不兼容的包...")
    run_command("pip uninstall -y yolov5 torchvision torch -q", "卸载yolov5、torchvision和torch")
    
    # 步骤2: 安装兼容的版本
    print("\n步骤2: 安装兼容的版本...")
    
    # 检查是否有GPU
    try:
        import torch
        has_gpu = torch.cuda.is_available()
    except:
        has_gpu = False
    
    if has_gpu:
        print("检测到GPU，安装CUDA版本...")
        run_command("pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118 -q", 
                   "安装PyTorch CUDA版本")
    else:
        print("未检测到GPU，安装CPU版本...")
        run_command("pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 -q", 
                   "安装PyTorch CPU版本")
    
    # 步骤3: 安装ultralytics（推荐用YOLOv8）
    print("\n步骤3: 安装ultralytics库...")
    run_command("pip install ultralytics -q", "安装ultralytics")
    
    # 步骤4: 验证安装
    print("\n步骤4: 验证安装...")
    try:
        import torch
        import torchvision
        from ultralytics import YOLO
        
        print(f"✓ PyTorch版本: {torch.__version__}")
        print(f"✓ torchvision版本: {torchvision.__version__}")
        print(f"✓ ultralytics已安装")
        print(f"✓ CUDA可用: {torch.cuda.is_available()}")
        
        print("\n" + "="*60)
        print("✓ 环境修复成功！")
        print("="*60)
        print("\n现在可以运行训练:")
        print("  python train_yolo.py")
        
        return True
        
    except Exception as e:
        print(f"✗ 验证失败: {e}")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)


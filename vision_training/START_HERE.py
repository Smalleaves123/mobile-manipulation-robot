"""
YOLO训练完整流程 - 一键启动
"""
import os
import sys
import subprocess
from pathlib import Path

def print_header(title):
    """打印标题"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def run_step(script_name, description):
    """运行一个步骤"""
    print_header(description)
    
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        print(f"✗ 找不到脚本: {script_path}")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(Path(__file__).parent),
            check=False
        )
        return result.returncode == 0
    except Exception as e:
        print(f"✗ 执行出错: {e}")
        return False

def main():
    """主流程"""
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║     YOLO交通信号灯检测模型训练 - 完整流程                   ║
║                                                            ║
║  本脚本将自动执行以下步骤:                                  ║
║  1️⃣  检查训练环境                                        ║
║  2️⃣  转换XML标注为YOLO格式                                ║
║  3️⃣  组织数据集                                           ║
║  4️⃣  训练模型                                             ║
║  5️⃣  分析结果                                             ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    input("按 Enter 开始... ")
    
    # 步骤1: 检查环境；不自动卸载或升级用户已有的 PyTorch 环境。
    if not run_step('check_environment.py', '步骤1️⃣  检查训练环境'):
        print("\n⚠️  环境检查未通过，请按 requirements.txt 手动安装后继续...")
    
    # 步骤2: 转换标注
    if not run_step('convert_xml_to_yolo.py', '步骤2️⃣  转换XML标注为YOLO格式'):
        print("\n✗ 标注转换失败！")
        return False
    
    # 步骤3: 组织数据集
    if not run_step('organize_dataset.py', '步骤3️⃣  组织数据集'):
        print("\n✗ 数据集组织失败！")
        return False
    
    # 步骤4: 训练模型
    if not run_step('train_yolo.py', '步骤4️⃣  训练YOLO模型'):
        print("\n✗ 模型训练失败！")
        return False
    
    # 步骤5: 分析结果
    if not run_step('analyze_results.py', '步骤5️⃣  分析训练结果'):
        print("\n⚠️  结果分析失败，但训练已完成")
    
    # 完成
    print_header("✓ 所有步骤完成！")
    
    print("""
📊 接下来可以做什么:

1. 查看训练结果:
   - 打开 runs/detect/traffic_detection/results.png 查看训练曲线
   - 打开 runs/detect/traffic_detection/confusion_matrix.png 查看混淆矩阵

2. 进行推理测试:
   python inference.py

3. 优化模型:
   - 如果精度不够，增加训练轮数或数据量
   - 如果速度不够，使用更小的模型（yolov8n）
   - 如果过拟合，增加早停耐心值或数据增强

4. 部署模型:
   - 导出为ONNX格式用于跨平台部署
   - 导出为TorchScript用于C++部署

祝你使用愉快！[object Object]""")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)


"""
一键运行YOLO训练流程
"""
import sys
import subprocess
from pathlib import Path

def run_script(script_name, description):
    """运行命令并显示进度"""
    print("\n" + "="*60)
    print(f"📍 {description}")
    print("="*60)
    
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / script_name)],
            cwd=str(Path(__file__).resolve().parent),
            check=True,
        )
        print(f"✓ {description} 完成！\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} 失败！")
        print(f"错误: {e}\n")
        return False

def main():
    """主流程"""
    base_dir = str(Path(__file__).resolve().parent)
    
    print("""
╔════════════════════════════════════════════════════════════╗
║          YOLO交通信号灯检测模型训练流程                      ║
║                                                            ║
║  本脚本将自动执行以下步骤:                                  ║
║  1. 转换XML标注为YOLO格式                                  ║
║  2. 组织数据集                                             ║
║  3. 安装依赖                                               ║
║  4. 训练模型                                               ║
║  5. 生成报告                                               ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    # 步骤1: 转换标注
    if not run_script('convert_xml_to_yolo.py', "步骤1: 转换XML标注为YOLO格式"):
        print("标注转换失败，请检查XML文件格式")
        return False
    
    # 步骤2: 组织数据集
    if not run_script('organize_dataset.py', "步骤2: 组织数据集"):
        print("数据集组织失败")
        return False
    
    # 步骤3: 训练模型；依赖安装由用户显式完成，避免训练流程修改环境。
    if not run_script('train_yolo.py', "步骤3: 训练YOLO模型"):
        print("模型训练失败")
        return False
    
    # 步骤5: 显示结果
    print("\n" + "="*60)
    print("✓ 训练流程完成！")
    print("="*60)
    
    # 查找最佳模型
    runs_dir = Path(base_dir) / 'runs' / 'detect' / 'traffic_detection'
    if runs_dir.exists():
        best_model = runs_dir / 'weights' / 'best.pt'
        if best_model.exists():
            print(f"\n✓ 最佳模型已保存: {best_model}")
            print(f"\n接下来可以运行推理:")
            print(f"  python inference.py")
        
        # 显示训练结果
        results_csv = runs_dir / 'results.csv'
        if results_csv.exists():
            print(f"\n✓ 训练结果已保存: {results_csv}")
    
    print("\n" + "="*60)
    print("📊 推荐后续操作:")
    print("="*60)
    print("""
1. 查看训练结果:
   - 打开 runs/detect/traffic_detection/results.png 查看训练曲线
   - 打开 runs/detect/traffic_detection/confusion_matrix.png 查看混淆矩阵

2. 进行推理测试:
   python inference.py

3. 优化模型:
   - 如果精度不够，增加训练轮数或数据量
   - 如果速度不够，使用更小的模型（yolov5n）
   - 如果过拟合，增加早停耐心值或数据增强

4. 部署模型:
   - 导出为ONNX格式用于跨平台部署
   - 导出为TorchScript用于C++部署
   - 导出为TFLite用于移动设备
    """)
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)


"""
分析和可视化YOLO训练结果
"""
import os
import csv
import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import pandas as pd

def load_results(results_csv):
    """加载训练结果CSV文件"""
    if not os.path.exists(results_csv):
        print(f"错误: 找不到结果文件 {results_csv}")
        return None
    
    df = pd.read_csv(results_csv)
    return df

def plot_training_curves(df, output_dir):
    """绘制训练曲线"""
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle('YOLO训练结果', fontsize=16)
    
    # 损失曲线
    if 'train/box_loss' in df.columns:
        axes[0, 0].plot(df['train/box_loss'], label='Train Box Loss')
        axes[0, 0].plot(df['val/box_loss'], label='Val Box Loss')
        axes[0, 0].set_xlabel('Epoch')
        axes[0, 0].set_ylabel('Loss')
        axes[0, 0].set_title('Box Loss')
        axes[0, 0].legend()
        axes[0, 0].grid(True)
    
    # 目标损失
    if 'train/obj_loss' in df.columns:
        axes[0, 1].plot(df['train/obj_loss'], label='Train Obj Loss')
        axes[0, 1].plot(df['val/obj_loss'], label='Val Obj Loss')
        axes[0, 1].set_xlabel('Epoch')
        axes[0, 1].set_ylabel('Loss')
        axes[0, 1].set_title('Objectness Loss')
        axes[0, 1].legend()
        axes[0, 1].grid(True)
    
    # 分类损失
    if 'train/cls_loss' in df.columns:
        axes[0, 2].plot(df['train/cls_loss'], label='Train Cls Loss')
        axes[0, 2].plot(df['val/cls_loss'], label='Val Cls Loss')
        axes[0, 2].set_xlabel('Epoch')
        axes[0, 2].set_ylabel('Loss')
        axes[0, 2].set_title('Classification Loss')
        axes[0, 2].legend()
        axes[0, 2].grid(True)
    
    # mAP50
    if 'metrics/mAP50' in df.columns:
        axes[1, 0].plot(df['metrics/mAP50'], label='mAP50', color='green')
        axes[1, 0].set_xlabel('Epoch')
        axes[1, 0].set_ylabel('mAP50')
        axes[1, 0].set_title('Mean Average Precision (IoU=0.50)')
        axes[1, 0].legend()
        axes[1, 0].grid(True)
    
    # mAP50-95
    if 'metrics/mAP50-95' in df.columns:
        axes[1, 1].plot(df['metrics/mAP50-95'], label='mAP50-95', color='orange')
        axes[1, 1].set_xlabel('Epoch')
        axes[1, 1].set_ylabel('mAP50-95')
        axes[1, 1].set_title('Mean Average Precision (IoU=0.50:0.95)')
        axes[1, 1].legend()
        axes[1, 1].grid(True)
    
    # 学习率
    if 'x/lr0' in df.columns:
        axes[1, 2].plot(df['x/lr0'], label='Learning Rate', color='red')
        axes[1, 2].set_xlabel('Epoch')
        axes[1, 2].set_ylabel('Learning Rate')
        axes[1, 2].set_title('Learning Rate Schedule')
        axes[1, 2].legend()
        axes[1, 2].grid(True)
    
    plt.tight_layout()
    output_path = os.path.join(output_dir, 'training_curves.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ 训练曲线已保存: {output_path}")
    plt.close()

def print_summary(df):
    """打印训练摘要"""
    print("\n" + "="*60)
    print("训练摘要")
    print("="*60)
    
    print(f"\n总轮数: {len(df)}")
    
    # 最佳mAP
    if 'metrics/mAP50-95' in df.columns:
        best_map = df['metrics/mAP50-95'].max()
        best_epoch = df['metrics/mAP50-95'].idxmax()
        print(f"最佳mAP50-95: {best_map:.4f} (第{best_epoch+1}轮)")
    
    if 'metrics/mAP50' in df.columns:
        best_map50 = df['metrics/mAP50'].max()
        print(f"最佳mAP50: {best_map50:.4f}")
    
    # 最终损失
    if 'val/box_loss' in df.columns:
        final_loss = df['val/box_loss'].iloc[-1]
        print(f"最终验证Box Loss: {final_loss:.4f}")
    
    # 训练时间
    if 'train/box_loss' in df.columns:
        print(f"\n损失统计:")
        print(f"  初始Box Loss: {df['train/box_loss'].iloc[0]:.4f}")
        print(f"  最终Box Loss: {df['train/box_loss'].iloc[-1]:.4f}")
        print(f"  改进: {(df['train/box_loss'].iloc[0] - df['train/box_loss'].iloc[-1]):.4f}")
    
    print("\n" + "="*60)

def plot_class_distribution(labels_dir):
    """绘制类别分布"""
    class_counts = {0: 0, 1: 0, 2: 0}
    class_names = {0: 'red_light', 1: 'green_light', 2: 'stop_sign'}
    
    # 统计所有标签文件
    for txt_file in Path(labels_dir).rglob('*.txt'):
        with open(txt_file, 'r') as f:
            for line in f:
                if line.strip():
                    class_id = int(line.split()[0])
                    if class_id in class_counts:
                        class_counts[class_id] += 1
    
    # 绘制柱状图
    fig, ax = plt.subplots(figsize=(10, 6))
    
    classes = [class_names[i] for i in sorted(class_counts.keys())]
    counts = [class_counts[i] for i in sorted(class_counts.keys())]
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
    
    bars = ax.bar(classes, counts, color=colors, edgecolor='black', linewidth=2)
    
    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    ax.set_ylabel('数量', fontsize=12)
    ax.set_title('类别分布统计', fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    return fig

def main():
    """主函数"""
    base_dir = Path(__file__).resolve().parent
    runs_dir = base_dir / 'runs' / 'detect' / 'traffic_detection'
    
    print("""
╔════════════════════════════════════════════════════════════╗
║              YOLO训练结果分析                               ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    # 加载训练结果
    results_csv = runs_dir / 'results.csv'
    df = load_results(str(results_csv))
    
    if df is None:
        print("无法找到训练结果，请先完成训练")
        return
    
    # 打印摘要
    print_summary(df)
    
    # 绘制训练曲线
    print("\n正在生成训练曲线...")
    plot_training_curves(df, str(runs_dir))
    
    # 绘制类别分布
    print("正在生成类别分布图...")
    labels_dir = Path(base_dir) / 'dataset' / 'labels'
    if labels_dir.exists():
        fig = plot_class_distribution(str(labels_dir))
        output_path = runs_dir / 'class_distribution.png'
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✓ 类别分布图已保存: {output_path}")
        plt.close()
    
    # 显示重要文件位置
    print("\n" + "="*60)
    print("重要文件位置:")
    print("="*60)
    print(f"最佳模型: {runs_dir / 'weights' / 'best.pt'}")
    print(f"最后模型: {runs_dir / 'weights' / 'last.pt'}")
    print(f"训练曲线: {runs_dir / 'training_curves.png'}")
    print(f"混淆矩阵: {runs_dir / 'confusion_matrix.png'}")
    print(f"结果CSV: {results_csv}")
    
    print("\n✓ 分析完成！")

if __name__ == '__main__':
    main()


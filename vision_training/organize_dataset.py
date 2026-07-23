"""
按照YOLO的要求组织数据集结构
标准结构:
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
"""
import os
import shutil
import random
from pathlib import Path

def organize_dataset(base_dir, output_dir, train_ratio=0.7, val_ratio=0.2, test_ratio=0.1):
    """
    组织数据集为YOLO格式
    """
    # 创建输出目录结构
    os.makedirs(os.path.join(output_dir, 'images', 'train'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'images', 'val'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'images', 'test'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'labels', 'train'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'labels', 'val'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'labels', 'test'), exist_ok=True)
    
    # 收集所有图像文件
    all_images = []
    categories = ['red_light', 'green_light', 'stop_sign', 'negative']
    
    for category in categories:
        category_dir = os.path.join(base_dir, category)
        if not os.path.exists(category_dir):
            print(f"警告: 找不到目录 {category_dir}")
            continue
        
        jpg_files = list(Path(category_dir).glob('*.jpg'))
        all_images.extend([(f, category) for f in jpg_files])
    
    print(f"找到总共 {len(all_images)} 张图像")
    
    # 随机打乱
    random.seed(42)
    random.shuffle(all_images)
    
    # 计算分割点
    train_count = int(len(all_images) * train_ratio)
    val_count = int(len(all_images) * val_ratio)
    
    train_images = all_images[:train_count]
    val_images = all_images[train_count:train_count + val_count]
    test_images = all_images[train_count + val_count:]
    
    print(f"训练集: {len(train_images)} 张")
    print(f"验证集: {len(val_images)} 张")
    print(f"测试集: {len(test_images)} 张")
    
    # 复制文件
    def copy_files(image_list, split_name):
        for img_path, category in image_list:
            # 复制图像
            img_dest = os.path.join(output_dir, 'images', split_name, img_path.name)
            shutil.copy2(img_path, img_dest)
            
            # 复制标签（如果存在）
            label_src = img_path.with_suffix('.txt')
            if label_src.exists():
                label_dest = os.path.join(output_dir, 'labels', split_name, label_src.name)
                shutil.copy2(label_src, label_dest)
            else:
                # 对于负样本，创建空的标签文件
                label_dest = os.path.join(output_dir, 'labels', split_name, img_path.stem + '.txt')
                open(label_dest, 'w').close()
    
    print("\n复制训练集...")
    copy_files(train_images, 'train')
    print("复制验证集...")
    copy_files(val_images, 'val')
    print("复制测试集...")
    copy_files(test_images, 'test')
    
    # 创建data.yaml文件
    # 使用相对 dataset 根目录的路径，避免把训练机器路径写入项目。
    yaml_content = """path: .
train: images/train
val: images/val
test: images/test

nc: 3
names: ['red_light', 'green_light', 'stop_sign']
"""
    
    yaml_path = os.path.join(output_dir, 'data.yaml')
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)
    
    print(f"\n✓ 数据集已组织完成！")
    print(f"✓ 配置文件已保存: {yaml_path}")

if __name__ == '__main__':
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent
    output_dir = base_dir / 'dataset'
    
    organize_dataset(str(base_dir), str(output_dir))


"""
将Pascal VOC格式的XML标注转换为YOLO格式的txt标注
"""
import os
import xml.etree.ElementTree as ET
from pathlib import Path

# 类别映射
CLASSES = {
    'red_light': 0,
    'green_light': 1,
    'stop_sign': 2
}

def convert_xml_to_yolo(xml_file, img_width, img_height):
    """
    将XML标注转换为YOLO格式
    YOLO格式: <class_id> <x_center> <y_center> <width> <height>
    其中坐标都是归一化的(0-1)
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    yolo_annotations = []
    
    for obj in root.findall('object'):
        class_name = obj.find('name').text
        
        # 跳过不在类别中的对象
        if class_name not in CLASSES:
            print(f"警告: 未知的类别 '{class_name}' 在文件 {xml_file}")
            continue
        
        class_id = CLASSES[class_name]
        
        bndbox = obj.find('bndbox')
        xmin = int(bndbox.find('xmin').text)
        ymin = int(bndbox.find('ymin').text)
        xmax = int(bndbox.find('xmax').text)
        ymax = int(bndbox.find('ymax').text)
        
        # 转换为YOLO格式
        x_center = (xmin + xmax) / 2.0 / img_width
        y_center = (ymin + ymax) / 2.0 / img_height
        width = (xmax - xmin) / img_width
        height = (ymax - ymin) / img_height
        
        # 确保坐标在0-1范围内
        x_center = max(0, min(1, x_center))
        y_center = max(0, min(1, y_center))
        width = max(0, min(1, width))
        height = max(0, min(1, height))
        
        yolo_annotations.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")
    
    return yolo_annotations

def process_directory(input_dir, output_dir):
    """
    处理整个目录，转换所有XML文件
    """
    os.makedirs(output_dir, exist_ok=True)
    
    xml_files = list(Path(input_dir).glob('*.xml'))
    
    for xml_file in xml_files:
        # 读取图像尺寸
        img_file = xml_file.with_suffix('.jpg')
        if not img_file.exists():
            print(f"警告: 找不到对应的图像文件 {img_file}")
            continue
        
        # 解析XML获取图像尺寸
        tree = ET.parse(xml_file)
        root = tree.getroot()
        size = root.find('size')
        img_width = int(size.find('width').text)
        img_height = int(size.find('height').text)
        
        # 转换标注
        yolo_annotations = convert_xml_to_yolo(xml_file, img_width, img_height)
        
        # 保存为txt文件
        output_file = Path(output_dir) / xml_file.stem
        output_file = output_file.with_suffix('.txt')
        
        with open(output_file, 'w') as f:
            for annotation in yolo_annotations:
                f.write(annotation + '\n')
        
        print(f"✓ 已转换: {xml_file.name} -> {output_file.name}")

if __name__ == '__main__':
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent
    
    # 转换各个类别的标注
    for category in ['red_light', 'green_light', 'stop_sign']:
        input_dir = base_dir / category
        output_dir = base_dir / category  # 直接覆盖到原目录
        
        if input_dir.exists():
            print(f"\n处理 {category} 类别...")
            process_directory(str(input_dir), str(output_dir))
    
    print("\n✓ 所有标注文件已转换完成！")


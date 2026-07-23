"""
使用训练好的YOLO模型进行推理
"""
import os
import cv2
import torch
from pathlib import Path

def inference_with_yolov5(model_path, image_path, conf_threshold=0.5):
    """
    使用YOLOv5进行推理
    """
    try:
        import yolov5
    except ImportError:
        raise RuntimeError("缺少 yolov5，请先安装 vision_training/requirements.txt")
    
    # 加载模型
    print(f"加载模型: {model_path}")
    model = yolov5.load(model_path)
    
    # 设置置信度阈值
    model.conf = conf_threshold
    
    # 推理
    print(f"处理图像: {image_path}")
    results = model(image_path)
    
    # 显示结果
    results.print()
    
    # 保存结果
    output_path = Path(image_path).stem + '_result.jpg'
    results.save(save_dir='.', exist_ok=True)
    
    print(f"✓ 结果已保存: {output_path}")
    
    return results

def inference_with_ultralytics(model_path, image_path, conf_threshold=0.5):
    """
    使用ultralytics库进行推理
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        raise RuntimeError("缺少 ultralytics，请先安装 vision_training/requirements.txt")
    
    # 加载模型
    print(f"加载模型: {model_path}")
    model = YOLO(model_path)
    
    # 推理
    print(f"处理图像: {image_path}")
    results = model.predict(
        source=image_path,
        conf=conf_threshold,
        save=True,
        project='inference_results',
        name='predictions'
    )
    
    print(f"✓ 结果已保存到: inference_results/predictions")
    
    return results

def batch_inference(model_path, image_dir, conf_threshold=0.5, output_dir='inference_results'):
    """
    批量推理
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        raise RuntimeError("缺少 ultralytics，请先安装 vision_training/requirements.txt")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 加载模型
    print(f"加载模型: {model_path}")
    model = YOLO(model_path)
    
    # 获取所有图像
    image_files = list(Path(image_dir).glob('*.jpg')) + list(Path(image_dir).glob('*.png'))
    
    print(f"找到 {len(image_files)} 张图像")
    
    # 批量推理
    for i, image_path in enumerate(image_files, 1):
        print(f"[{i}/{len(image_files)}] 处理: {image_path.name}")
        
        results = model.predict(
            source=str(image_path),
            conf=conf_threshold,
            save=False,
            verbose=False
        )
        
        # 绘制结果
        if results[0].boxes is not None:
            annotated_frame = results[0].plot()
            output_path = os.path.join(output_dir, f'result_{image_path.stem}.jpg')
            cv2.imwrite(output_path, annotated_frame)
    
    print(f"✓ 所有结果已保存到: {output_dir}")

def detect_from_camera(model_path, conf_threshold=0.5):
    """
    从摄像头实时检测
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        raise RuntimeError("缺少 ultralytics，请先安装 vision_training/requirements.txt")
    
    # 加载模型
    print(f"加载模型: {model_path}")
    model = YOLO(model_path)
    
    # 打开摄像头
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("错误: 无法打开摄像头")
        return
    
    print("按 'q' 退出")
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            break
        
        # 推理
        results = model.predict(source=frame, conf=conf_threshold, verbose=False)
        
        # 绘制结果
        annotated_frame = results[0].plot()
        
        # 显示
        cv2.imshow('YOLO Detection', annotated_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    # 模型路径（训练完成后会生成）
    base_dir = Path(__file__).resolve().parent
    default_weights = base_dir / 'runs' / 'detect' / 'traffic_detection' / 'weights' / 'best.pt'
    # 若默认权重不存在，则尝试搜索最近一次运行的best.pt
    if not default_weights.exists():
        candidates = sorted(base_dir.glob('runs/detect/*/weights/best.pt'), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            default_weights = candidates[0]
    model_path = str(default_weights)
    
    # 选择推理方式
    print("选择推理方式:")
    print("1. 单张图像推理")
    print("2. 批量推理")
    print("3. 实时摄像头检测")
    
    choice = input("请选择 (1/2/3): ").strip()
    
    if choice == '1':
        image_path = input("请输入图像路径: ").strip()
        if os.path.exists(image_path):
            inference_with_ultralytics(model_path, image_path)
        else:
            print(f"错误: 找不到图像 {image_path}")
    
    elif choice == '2':
        image_dir = input("请输入图像目录: ").strip()
        if os.path.exists(image_dir):
            batch_inference(model_path, image_dir)
        else:
            print(f"错误: 找不到目录 {image_dir}")
    
    elif choice == '3':
        detect_from_camera(model_path)
    
    else:
        print("无效的选择")


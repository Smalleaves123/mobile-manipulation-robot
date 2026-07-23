#!/usr/bin/env python3
"""Export a trained YOLO checkpoint to the robot deployment directory.

Training dependencies stay under ``vision_training``.  The robot only needs
the generated OpenVINO files under ``detection/best_openvino_model``.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def find_export_directory(export_result) -> Path:
    """Normalize the path returned by different Ultralytics versions."""
    result_path = Path(str(export_result))
    if result_path.is_file():
        return result_path.parent
    return result_path


def export_openvino(weights: Path, output_dir: Path, imgsz: int = 640) -> Path:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(
            "缺少 ultralytics，请先安装 vision_training/requirements.txt"
        ) from exc

    if not weights.is_file():
        raise FileNotFoundError(f"找不到训练权重: {weights}")

    model = YOLO(str(weights))
    exported = model.export(format="openvino", imgsz=imgsz, device="cpu")
    source_dir = find_export_directory(exported)

    xml_files = list(source_dir.glob("*.xml"))
    bin_files = list(source_dir.glob("*.bin"))
    if not xml_files or not bin_files:
        raise RuntimeError(f"导出目录缺少 OpenVINO xml/bin: {source_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(xml_files[0], output_dir / "best.xml")
    shutil.copy2(bin_files[0], output_dir / "best.bin")
    metadata = source_dir / "metadata.yaml"
    if metadata.exists():
        shutil.copy2(metadata, output_dir / "metadata.yaml")

    return output_dir


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    default_weights = (
        project_root
        / "vision_training"
        / "runs"
        / "detect"
        / "traffic_detection"
        / "weights"
        / "best.pt"
    )
    default_output = project_root / "detection" / "best_openvino_model"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=default_weights)
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()

    weights = args.weights if args.weights.is_absolute() else project_root / args.weights
    output = args.output if args.output.is_absolute() else project_root / args.output
    result = export_openvino(weights, output, imgsz=max(32, args.imgsz))
    print(f"OpenVINO 部署模型已写入: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

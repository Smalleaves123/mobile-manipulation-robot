#!/usr/bin/env python3
"""Create a vendor-compatible Nav2 parameter file using the custom A* plugin.

The vendor file is intentionally read from the installed ``iqr_tb4_navigation``
package and never modified.  The generated file is an application artifact
that keeps every vendor parameter and replaces only planner_server.GridBased.
"""

import argparse
from pathlib import Path

import yaml


def default_vendor_params() -> Path:
    from ament_index_python.packages import get_package_share_directory

    return (
        Path(get_package_share_directory("iqr_tb4_navigation"))
        / "config"
        / "nav2.yaml"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        type=Path,
        default=None,
        help="vendor Nav2 YAML; defaults to iqr_tb4_navigation/config/nav2.yaml",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("config/nav2_custom.yaml"),
        help="generated application YAML path",
    )
    parser.add_argument("--use-8-neighbors", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--allow-unknown",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="allow traversal through NO_INFORMATION costmap cells",
    )
    parser.add_argument("--cost-weight", type=float, default=0.5)
    parser.add_argument("--timeout-ms", type=float, default=5000.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    base_path = args.base or default_vendor_params()
    with base_path.open("r", encoding="utf-8") as stream:
        params = yaml.safe_load(stream)

    if not isinstance(params, dict):
        raise ValueError(f"Nav2 参数文件不是 YAML mapping: {base_path}")

    planner_server = params.setdefault("planner_server", {})
    ros_parameters = planner_server.setdefault("ros__parameters", {})
    ros_parameters["planner_plugins"] = ["GridBased"]
    ros_parameters["GridBased"] = {
        "plugin": "my_nav2_planner/MyAStarPlanner",
        "use_8_neighbors": bool(args.use_8_neighbors),
        "allow_unknown": bool(args.allow_unknown),
        "cost_weight": max(0.0, min(1.0, float(args.cost_weight))),
        "timeout_ms": max(1.0, float(args.timeout_ms)),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(params, stream, sort_keys=False, allow_unicode=True)
    print(f"generated: {args.output}")
    print(f"base: {base_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Mobile Manipulation Robot

> An integrated ROS 2 mobile-manipulation robot application.

This repository presents a complete robot application rather than a single
standalone algorithm. It combines autonomous navigation, a custom Nav2 global
planner, visual perception, PX100 arm control, object grasping and placement,
traffic-light/STOP-sign interaction, and a deployable vision-training
pipeline. The project is designed for a TurtleBot4 + PX100 mobile-manipulation
workcell, while keeping the application layer organized as a reusable robotics
system.

## System Capabilities

- Mobile navigation with Nav2, fixed mission waypoints, obstacle-layer
  avoidance, replanning, and an optional custom A* planner.
- Object grasping with ArUco, marker-free box localization through SAM or
  HSV/PnP fallback, fixed-target compatibility mode, and optional gripper
  state verification.
- Arm placement with command-compatible behavior and optional joint-state
  verification.
- OpenVINO traffic-light and STOP-sign detection with temporal filtering and
  stop/resume control during navigation.
- Integrated YOLO dataset, training, and OpenVINO export tools for extending
  the perception model.

The application capability mapping is documented in
[Capability coverage](#capability-coverage). The original
fixed-route and fixed-target algorithms remain available as deployment
fallbacks, while the extended perception and planning paths are provided for
randomized and marker-free demonstrations.

## Implementation boundary

The official TurtleBot4, PX100, RealSense, pan-tilt and IMU packages are
installed in the robot's ROS2 workspace. This repository contains the team
application layer and keeps the original ROS scripts as deployment fallbacks.
The sibling `../src/` directory belongs to the robot's pre-installed hardware
workspace; it is a reference dependency and must not be modified here.

## Project Structure

```
mobile-manipulation-robot/
│
├── arm/                # Robotic arm control and grasping scripts
│   ├── arm_controller.py
│   ├── grasping_ok.py
│   ├── place_the_box.py
│   ├── ...
│
├── aruco_tracker/      # Optional ROS 2 ArUco tracker package
│   ├── aruco_tracker/
│   │   └── aruco_node.py
│   ├── ...
│
├── detection/          # Object detection and traffic light recognition
│   ├── inference_nuc.py        # Inference script for NUC
│   ├── visual_detection_ros.py # Non-aruco marker detection
│   ├── ...
│
├── vision_training/    # 视觉数据集、训练脚本、训练结果与部署导出
│   ├── dataset/
│   ├── runs/
│   ├── train_yolo.py
│   └── export_openvino.py
│
├── my_nav2_planner/
│   ├── CMakeLists.txt
│   ├── package.xml
│   ├── global_planner_plugin.xml
│   ├── include/
│   │   └── my_nav2_planner/
│   │       └── my_astar_planner.hpp
│   └── src/
│       └── my_astar_planner.cpp
│
├── planning/           # Main navigation package
│   ├── scripts/
│   │   ├── navigation.py      # Full-process navigation
│   │   ├── simple_nav.py      # Single-point navigation
│   │   ├── stop_at_rviz.py    # RViz navigation with traffic light support
│   │   └── read_pose.py       # Read waypoint data
│   ├── launch/
│   │   ├── navigation.launch.py   # Main navigation launch file
│   │   ├── navigation_full.launch.py # Navigation + task handshake
│   │   ├── supplement.launch.py   # Arm and perception launch
│   │   └── full_project.launch.py # Single complete mission entry point
│   ├── map/                # Map files
│   ├── ...
│
├── yolo_detection/     # Collection of YOLO dataset
│   └── collection.py
│
├── yolo_test/          # YOLO test models and results
│   ├── yolov8n.pt
│   └── yolov8n_openvino_model/
│
└── tools/
    └── merge_nav2_params.py # Generate a custom-planner Nav2 config
```

## Common Scripts and Launch Commands

### Automatic Navigation Process
```bash
ros2 launch iqr_tb4_bringup bringup.launch.py
ros2 launch planning navigation.launch.py
ros2 launch planning supplement.launch.py
```

### 1. System Bringup
```bash
ros2 launch iqr_tb4_bringup bringup.launch.py
```

### 2. Start Arm Controller
```bash
python3 arm/arm_controller.py
```

### 3. Start Grasping/Placing
```bash
python3 arm/grasping_ok.py
python3 arm/place_the_box.py
```

### 4. Navigation Process
```bash
ros2 launch iqr_tb4_navigation localization.launch.py map:=planning/map/map.yaml
ros2 launch iqr_tb4_navigation nav2.launch.py
python3 planning/scripts/navigation.py
```

### 5. Start Traffic Light Detection
```bash
python3 detection/inference_nuc.py
```

### 6. Vision training and deployment

训练项目已经和机器人应用代码放在同一个应用文件夹内：

```bash
cd /home/tony/ros2_ws/src/mobile-manipulation-robot/vision_training
python3 train_yolo.py
```

训练完成后，将 YOLO 权重导出为机器人端使用的 OpenVINO 模型：

```bash
python3 export_openvino.py \
  --weights runs/detect/traffic_detection/weights/best.pt
```

导出结果写入 `detection/best_openvino_model/`，由
`detection/inference_nuc.py` 在机器人上加载。训练依赖只属于
`vision_training`，机器人运行主任务不需要安装完整训练环境。

## Complete mission entry point

The legacy fixed-route node remains available as
`planning/scripts/navigation.py`. The complete mission adapter is
`planning/scripts/navigation_full.py`. For the complete application, use the
single launch entry point:

```bash
ros2 launch iqr_tb4_bringup bringup.launch.py
ros2 launch planning full_project.launch.py
```

The application launch starts the RealSense and pan-tilt drivers by default,
then the traffic detector, arm task nodes, Nav2, and the mission state
machine. Component switches are also exposed for staged demonstrations. If
either driver is already running, disable only that part:

```bash
ros2 launch planning full_project.launch.py \
  start_camera:=false start_pan_tilt:=false
```

The old two-launch sequence remains available for staged debugging.

The default route still uses the existing tested waypoints. The mission node
pauses and resumes the same waypoint when `/traffic_light/stop_control`
changes, waits for `/grasp/success` after waypoint 4, and waits for
`/place/success` after waypoint 5.

`navigation_full.launch.py` forwards the official `iqr_tb4_navigation` `params_file`
argument. To use `MyAStarPlanner`, first build a project-side copy of the
vendor parameters. The helper reads the installed vendor file and never
modifies it:

```bash
cd /home/tony/ros2_ws
colcon build --packages-select planning my_nav2_planner
source install/setup.bash
cd /home/tony/ros2_ws/src/mobile-manipulation-robot
python3 tools/merge_nav2_params.py \
  --output /home/tony/ros2_ws/src/mobile-manipulation-robot/config/nav2_custom.yaml
ros2 launch planning full_project.launch.py \
  params_file:=/home/tony/ros2_ws/src/mobile-manipulation-robot/config/nav2_custom.yaml
```

The launch file defaults to the vendor `nav2.yaml`, so the original planner
remains the safe fallback until the custom planner parameter file is selected.

## Grasp vision modes

`arm/grasping_ok.py` keeps ArUco as the default deployment mode:

```bash
python3 arm/grasping_ok.py --ros-args -p vision_mode:=aruco
```

The same state machine can start the existing box detector instead:

```bash
python3 arm/grasping_ok.py --ros-args -p vision_mode:=box
```

For a complete marker-free fallback demonstration, use `vision_mode:=auto`.
The node tries ArUco first, then automatically restarts with the SAM/HSV/PnP
box pipeline if no stable marker target is found:

```bash
ros2 launch planning full_project.launch.py grasp_vision_mode:=auto
```

The box detector first uses SAM when its checkpoint is available. If the
checkpoint or `segment_anything` is absent, it automatically falls back to
the existing HSV white-region mask and PnP pipeline, so the PoseArray topic
and grasp state machine remain usable on the robot.

For a fixed-object fallback, enable it explicitly and set the calibrated
target in the PX100 base frame:

```bash
python3 arm/grasping_ok.py --ros-args \
  -p allow_fixed_fallback:=true \
  -p fixed_target_x:=0.20 -p fixed_target_y:=0.0 -p fixed_target_z:=0.05
```

The default `grasp_verification:=commanded` preserves the original behavior.
On the robot, `grasp_verification:=joint_state` enables an optional heuristic
using `/joint_states` (configurable for older images); this is better than
unconditional success but is not a force/tactile sensor measurement.

Placement has the same compatibility boundary: `place_verification:=commanded`
keeps the legacy command-complete behavior, while
`place_verification:=joint_state` verifies that the gripper opened before
publishing `/place/success=True`. This is actuator-state verification, not
direct object-in-bin perception.

The complete navigator also has a per-waypoint navigation timeout and retry
limit. It stops with an explicit timeout if navigation, grasping, or placing
never completes, instead of waiting forever. It
publishes `/mission/status` and `/mission/success` for final demonstrations
and failure diagnosis.
抓取节点还发布 `/grasp/status`，会区分视觉搜索超时、IK 失败、夹爪核验失败
和成功完成，便于现场判断问题是在视觉、运动学还是夹爪阶段。

## Capability coverage

| Capability | Application path | Status |
|---|---|---|
| Fixed-obstacle navigation | Nav2 waypoint mission with the original map and route | covered |
| Random-obstacle navigation | Nav2 costmap obstacle avoidance and replanning | implemented; requires physical validation |
| Custom global planner | `my_nav2_planner/MyAStarPlanner` plugin | implemented; enable it in the robot Nav2 parameter file |
| Fixed-position pick & place | Visual grasp with explicit fixed fallback, then place | covered |
| Random-position pick & place | ArUco target stability filtering and box PnP mode | implemented; requires physical calibration |
| Marker-free pick & place | `grasp_vision_mode:=box`, SAM or HSV/PnP fallback | implemented; requires physical calibration |
| Traffic-light/STOP-sign detection | OpenVINO detector and temporal stop decision | covered |
| Stop/resume during navigation | `/traffic_light/stop_control` cancels and resumes the same waypoint | covered |

The randomized capabilities are described as “implemented” rather than
guaranteed: final behavior still depends on physical calibration and the
actual obstacle/object arrangement.

## Local verification boundary

This macOS checkout does not contain the robot's ROS2 runtime, so local
verification is limited to Python syntax compilation and static inspection.
ROS actions, TF, OpenVINO/SAM loading, the Nav2 plugin build and real hardware
still need to be verified on the NUC. The fixed route and fixed grasp target
remain available as deployment fallbacks.

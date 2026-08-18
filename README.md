# Mobile Manipulation Robot

> **A ROS 2 mobile manipulation system built and validated on a real TurtleBot4 + PX100 platform.**

This project implements an integrated **perception–navigation–decision–manipulation** pipeline for a mobile manipulation robot.

The system combines:

* TurtleBot4 autonomous navigation based on ROS 2 and Nav2
* a custom A* global planner implemented as a Nav2 plugin
* waypoint-based mission execution and task-state management
* real-time obstacle avoidance and replanning through the Nav2 costmap
* PX100 robotic-arm grasping and placement
* ArUco-based and marker-free object localization
* PnP-based 6D pose estimation and ROS TF coordinate transformation
* OpenVINO-based traffic-light and STOP-sign perception
* navigation stop/resume interaction triggered by visual perception
* YOLO training and OpenVINO deployment tools

The complete task pipeline has been tested on the **physical TurtleBot4 + PX100 robot**, including autonomous navigation, visual perception, object grasping, placement, and navigation interruption/recovery.

---

## 1. System Overview

The project is designed as a complete mobile manipulation application rather than a collection of isolated algorithms.

A typical mission follows the pipeline:

```text
                    +----------------------+
                    |   RGB / RGB-D Camera |
                    +----------+-----------+
                               |
               +---------------+---------------+
               |                               |
               v                               v
      Object Localization              Traffic Perception
   ArUco / SAM / HSV + PnP           YOLO + OpenVINO
               |                               |
               v                               v
         Target Pose                  Stop / Resume Signal
               |                               |
               v                               |
          ROS 2 TF                            |
               |                               |
               v                               v
        PX100 Base Frame              Mission State Machine
               |                               |
               v                               v
       Numerical IK                   Nav2 Navigation
               |                               |
               v                               v
      Grasp / Place Action <---------- Waypoint Mission
```

At the system level, navigation first brings the robot into the manipulation workspace. Visual perception then estimates the target pose, transforms it into the manipulator base frame, and triggers grasping. After the manipulation task succeeds, the robot continues its navigation mission.

---

## 2. Hardware Platform

The system was developed and tested using:

* **TurtleBot4** mobile robot
* **Interbotix PX100** robotic arm
* **Intel RealSense** RGB-D camera
* pan-tilt camera mechanism
* Intel NUC / onboard computing platform

The original TurtleBot4, PX100, RealSense, pan-tilt and related ROS 2 hardware packages are provided by their corresponding hardware stacks.

This repository mainly contains the **application-level modules developed for the integrated mobile-manipulation task**.

---

## 3. Main Capabilities

### 3.1 Autonomous Navigation

The mobile base uses ROS 2 Nav2 for localization, global planning, local obstacle avoidance and motion execution.

The mission layer supports:

* multi-waypoint navigation
* navigation timeout handling
* failed-goal retry
* pause and recovery
* task-triggered grasping and placement
* traffic-triggered navigation interruption
* mission status reporting

The navigation state machine coordinates the mobile base with perception and manipulation modules instead of allowing each module to run independently.

---

### 3.2 Custom Nav2 A* Global Planner

A custom global planner is implemented according to the:

```cpp
nav2_core::GlobalPlanner
```

interface and exported through ROS 2 `pluginlib`.

The planner directly operates on the Nav2 global costmap and supports:

* 4-connected or 8-connected grid search
* Euclidean heuristic
* diagonal motion cost
* obstacle inflation compatibility
* costmap-based traversal penalties
* configurable unknown-space handling
* diagonal corner-cutting prevention
* planning timeout
* ROS 2 / Nav2 plugin integration

The search cost is based on both geometric path length and the Nav2 costmap value:

```text
g_new =
    g_current
    + geometric_motion_cost
    + costmap_penalty
```

Therefore, the planner can prefer lower-cost regions instead of considering only geometric distance.

For 8-connected search, diagonal movement is additionally checked to prevent the path from passing through obstacle corners.

The custom planner can be selected through the Nav2 parameter file while the original Nav2 planner remains available as a fallback.

---

## 4. Mission State Machine

The integrated task is controlled by a ROS 2 mission state machine.

The mission contains several navigation waypoints. At specific waypoints, navigation is suspended and a manipulation task is triggered.

Typical execution:

```text
START
  |
  v
Navigate waypoint 1
  |
  v
Navigate waypoint 2
  |
  v
...
  |
  v
Reach grasp waypoint
  |
  v
Trigger grasp task
  |
  v
Wait for /grasp/success
  |
  v
Continue navigation
  |
  v
Reach placement waypoint
  |
  v
Trigger placement task
  |
  v
Wait for /place/success
  |
  v
Continue mission
  |
  v
MISSION COMPLETE
```

The navigation node communicates with Nav2 through the `NavigateToPose` action interface.

Because ROS 2 actions are asynchronous, the mission implementation also maintains a goal sequence identifier to prevent delayed responses from an old goal from modifying the state of a newer goal.

This is particularly important when a navigation goal is cancelled by a traffic signal before the original action response has returned.

---

## 5. Traffic-Light and STOP-Sign Interaction

The project includes a visual traffic-perception pipeline for navigation interaction.

The perception pipeline is:

```text
Camera
  |
  v
YOLO detector
  |
  v
OpenVINO inference
  |
  v
Traffic-light / STOP classification
  |
  v
Temporal decision filtering
  |
  v
/traffic_light/stop_control
  |
  v
Mission state machine
```

When a stop condition is detected, the current Nav2 navigation goal is cancelled and the robot enters a stopped state.

When the stop condition disappears, the mission controller resends the current waypoint and continues the task.

This implements navigation-level stop/resume behavior without directly coupling the vision node to low-level motor commands.

---

## 6. Object Localization

The project supports multiple object-localization modes.

### 6.1 ArUco-Based Localization

ArUco markers can be used to provide a reliable reference target during development and controlled experiments.

The detected target pose is published through ROS 2 and transformed into the PX100 base coordinate frame before grasp planning.

---

### 6.2 Marker-Free Box Localization

The system also implements object localization without relying on artificial fiducial markers.

The marker-free pipeline is designed for the known box target used in the experiment.

```text
RGB Image
   |
   v
Region of Interest
   |
   v
HSV-based candidate extraction
   |
   +-------------------+
   |                   |
   | SAM available     | SAM unavailable
   v                   v
SAM segmentation     HSV mask
   |                   |
   +---------+---------+
             |
             v
       Object contour
             |
             v
      minAreaRect
             |
             v
       Four corners
             |
             v
        solvePnP
             |
             v
     Camera-frame pose
```

The method does **not** assume a completely unknown object.

Instead, it uses task-specific priors including:

* approximate object color
* rectangular geometry
* known physical dimensions
* calibrated camera parameters

Therefore, “marker-free” here means that the manipulation task does not require an ArUco or similar artificial marker attached to the object.

---

## 7. PnP Pose Estimation

For a known object geometry, the detected image points and corresponding object-frame points are used to estimate the object pose.

The camera projection model is:

```text
s [u v 1]^T = K [R | t] [X Y Z 1]^T
```

where:

* `(X, Y, Z)` is a known point in the object coordinate frame
* `(u, v)` is its detected image coordinate
* `K` is the calibrated camera intrinsic matrix
* `R` and `t` represent the object pose relative to the camera

OpenCV `solvePnP` is used to recover the pose.

The estimated target is subsequently transformed into the robot-arm coordinate frame through ROS 2 TF.

---

## 8. Coordinate Transformation

Visual perception produces a target pose in the camera coordinate frame, while robotic-arm control requires the target in the PX100 base frame.

The required transformation can be written as:

```text
T_base_object =
    T_base_camera
    *
    T_camera_object
```

ROS 2 TF is used to query the camera-to-arm transformation.

The resulting pose is checked against the manipulator workspace before inverse kinematics is executed.

---

## 9. Target Stability Filtering

Directly executing a grasp from a single visual frame can be unreliable because pose estimation may fluctuate.

The grasping module therefore performs multi-frame target stability checking.

A target is accepted only after its estimated three-dimensional position remains sufficiently stable over consecutive frames.

The default implementation uses approximately:

```text
position tolerance: 0.02 m
stable frames:      6
```

This acts as a simple perception gate before manipulation starts.

The purpose is not general object tracking, but to determine whether the current visual pose is sufficiently stable for a discrete grasp operation.

---

## 10. PX100 Grasping

After the target is transformed into the PX100 base frame, the grasping module generates a sequence of manipulation targets.

Typical grasp sequence:

```text
Target detection
      |
      v
Workspace check
      |
      v
Hover target
      |
      v
Numerical IK
      |
      v
Move above object
      |
      v
Lower end effector
      |
      v
Close gripper
      |
      v
Lift object
      |
      v
Publish grasp result
```

The manipulator uses numerical inverse kinematics based on the PX100 kinematic model.

Multiple initial joint configurations are used to improve solver robustness.

A previously successful solution can also be reused as a warm start for the next IK calculation.

If the target is unreachable or the IK solver fails, the state machine can return to target acquisition instead of blindly executing the motion.

---

## 11. Placement

The placement module controls the PX100 to move the object to a predefined placement configuration.

The placement task is coordinated with the main mission through ROS 2 topics.

The navigation state machine continues only after receiving the placement completion signal.

This ensures explicit synchronization between navigation and manipulation.

---

## 12. Real-Robot Validation

The integrated system has been validated on the physical TurtleBot4 + PX100 platform.

The hardware experiments cover the complete application chain:

```text
Navigation
    ↓
Obstacle avoidance
    ↓
Traffic perception
    ↓
Stop / resume
    ↓
Reach manipulation area
    ↓
Object localization
    ↓
TF transformation
    ↓
Inverse kinematics
    ↓
Grasp
    ↓
Continue navigation
    ↓
Placement
```

The project therefore focuses not only on individual algorithm implementation, but also on practical issues that appear when multiple robotic subsystems are combined on real hardware, including:

* coordinate-frame consistency
* visual-pose fluctuation
* manipulator workspace constraints
* asynchronous ROS 2 actions
* navigation interruption and recovery
* perception/manipulation synchronization
* task timeout and retry handling

---

## 13. Project Structure

```text
mobile-manipulation-robot/
│
├── arm/
│   ├── arm_controller.py
│   ├── grasping_ok.py
│   ├── place_the_box.py
│   └── ...
│
├── aruco_tracker/
│   └── aruco_tracker/
│       └── aruco_node.py
│
├── detection/
│   ├── inference_nuc.py
│   ├── visual_detection_ros.py
│   └── ...
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
├── planning/
│   ├── scripts/
│   │   ├── navigation.py
│   │   ├── navigation_full.py
│   │   ├── simple_nav.py
│   │   ├── stop_at_rviz.py
│   │   └── read_pose.py
│   │
│   ├── launch/
│   │   ├── navigation.launch.py
│   │   ├── navigation_full.launch.py
│   │   ├── supplement.launch.py
│   │   └── full_project.launch.py
│   │
│   └── map/
│
├── vision_training/
│   ├── dataset/
│   ├── runs/
│   ├── train_yolo.py
│   └── export_openvino.py
│
├── yolo_detection/
│   └── collection.py
│
├── yolo_test/
│   ├── yolov8n.pt
│   └── yolov8n_openvino_model/
│
├── tools/
│   └── merge_nav2_params.py
│
└── README.md
```

---

## 14. Running the Robot

### 14.1 Build the workspace

```bash
cd ~/ros2_ws
colcon build
source install/setup.bash
```

---

### 14.2 Start TurtleBot4 hardware

```bash
ros2 launch iqr_tb4_bringup bringup.launch.py
```

---

### 14.3 Start the complete mission

```bash
ros2 launch planning full_project.launch.py
```

The complete launch configuration can start:

* camera drivers
* pan-tilt drivers
* traffic perception
* robotic-arm task nodes
* Nav2
* mission state machine

If part of the hardware stack is already running, individual modules can be disabled through launch parameters.

Example:

```bash
ros2 launch planning full_project.launch.py \
    start_camera:=false \
    start_pan_tilt:=false
```

---

## 15. Using the Custom A* Planner

Build the planner and navigation packages:

```bash
cd ~/ros2_ws
colcon build --packages-select planning my_nav2_planner
source install/setup.bash
```

Generate a project-side Nav2 configuration:

```bash
cd ~/ros2_ws/src/mobile-manipulation-robot

python3 tools/merge_nav2_params.py \
    --output config/nav2_custom.yaml
```

Start the complete system using the custom planner:

```bash
ros2 launch planning full_project.launch.py \
    params_file:=$(pwd)/config/nav2_custom.yaml
```

The original Nav2 configuration can still be used when the custom planner is not selected.

---

## 16. Grasp Vision Modes

### ArUco mode

```bash
python3 arm/grasping_ok.py \
    --ros-args \
    -p vision_mode:=aruco
```

### Marker-free box mode

```bash
python3 arm/grasping_ok.py \
    --ros-args \
    -p vision_mode:=box
```

### Automatic mode

```bash
ros2 launch planning full_project.launch.py \
    grasp_vision_mode:=auto
```

In automatic mode, the system can first attempt the standard visual target and switch to the marker-free box-localization pipeline when necessary.

---

## 17. Vision Training

The repository also contains the dataset preparation, YOLO training and deployment pipeline used by the traffic-perception module.

Train the detector:

```bash
cd vision_training
python3 train_yolo.py
```

Export the trained model to OpenVINO:

```bash
python3 export_openvino.py \
    --weights runs/detect/traffic_detection/weights/best.pt
```

The OpenVINO model can then be deployed on the robot-side computing platform for inference.

This separates the model-training environment from the lightweight robot deployment environment.

---

## 18. Design Scope

This project follows a modular mobile-manipulation architecture.

The current implementation intentionally separates:

* global mobile navigation
* local obstacle avoidance
* visual object localization
* robotic-arm manipulation

The custom A* planner is a **2D costmap-based global planner**. Dynamic obstacle response is mainly handled through Nav2 costmap updates, local control and replanning; the project does not claim an explicit space-time dynamic-obstacle prediction algorithm.

Similarly, marker-free localization is a task-oriented perception solution using geometric and appearance priors rather than a general-purpose category-level 6D object-pose estimator.

The manipulation architecture freezes the mobile base before grasp execution rather than jointly optimizing base and manipulator motion.

These choices keep the system robust and interpretable for the target physical-robot task while providing clear interfaces for future extensions.

---

## 19. Possible Extensions

Several extensions can further improve the system:

* depth-assisted object pose estimation
* visual servoing for final grasp alignment
* force/tactile-based grasp verification
* MoveIt 2 based collision-aware arm planning
* joint mobile-base and manipulator planning
* explicit dynamic-obstacle trajectory prediction
* behavior-tree based task management
* stronger failure recovery policies
* general-purpose 6D object-pose estimation

---

## 20. Summary

This project demonstrates an end-to-end mobile manipulation system on a real TurtleBot4 + PX100 platform.

Rather than focusing only on a single planning or perception algorithm, the project integrates:

```text
Perception
   +
Navigation
   +
Task Decision
   +
Coordinate Transformation
   +
Manipulation
   =
Real-Robot Closed-Loop Mobile Manipulation
```

The main goal of the project is to explore how perception, planning and control modules can be organized into a reliable autonomous robotic system and validated through physical robot experiments.

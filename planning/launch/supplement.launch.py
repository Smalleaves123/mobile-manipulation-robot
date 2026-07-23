#!/usr/bin/env python3
"""Launch the application-side arm and perception components.

The vendor robot bringup remains external; this file only starts team code.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    # 核心路径配置
    project_root = '/home/tony/ros2_ws/src/mobile-manipulation-robot'

    grasp_vision_mode = LaunchConfiguration('grasp_vision_mode')
    allow_fixed_fallback = LaunchConfiguration('allow_fixed_fallback')
    fixed_target_x = LaunchConfiguration('fixed_target_x')
    fixed_target_y = LaunchConfiguration('fixed_target_y')
    fixed_target_z = LaunchConfiguration('fixed_target_z')
    grasp_verification = LaunchConfiguration('grasp_verification')
    gripper_state_topic = LaunchConfiguration('gripper_state_topic')
    grasp_search_timeout_sec = LaunchConfiguration('grasp_search_timeout_sec')
    target_stability_tolerance = LaunchConfiguration('target_stability_tolerance')
    target_stability_frames = LaunchConfiguration('target_stability_frames')
    pan_tilt_pitch_deg = LaunchConfiguration('pan_tilt_pitch_deg')
    pan_tilt_settle_sec = LaunchConfiguration('pan_tilt_settle_sec')
    detector_startup_sec = LaunchConfiguration('detector_startup_sec')
    max_ik_retries = LaunchConfiguration('max_ik_retries')
    gripper_object_gap = LaunchConfiguration('gripper_object_gap')
    gripper_open_position = LaunchConfiguration('gripper_open_position')
    gripper_close_position = LaunchConfiguration('gripper_close_position')
    grasp_verification_timeout_sec = LaunchConfiguration('grasp_verification_timeout_sec')
    place_verification = LaunchConfiguration('place_verification')
    place_open_tolerance = LaunchConfiguration('place_open_tolerance')
    place_verification_timeout_sec = LaunchConfiguration('place_verification_timeout_sec')
    traffic_model_path = LaunchConfiguration('traffic_model_path')
    traffic_image_topic = LaunchConfiguration('traffic_image_topic')
    traffic_device = LaunchConfiguration('traffic_device')
    traffic_conf_threshold = LaunchConfiguration('traffic_conf_threshold')
    traffic_filter_window_size = LaunchConfiguration('traffic_filter_window_size')
    traffic_stop_threshold = LaunchConfiguration('traffic_stop_threshold')

    # 1. 机械臂控制器 | 命令行: python3 /home/tony/ros2_ws/src/mobile-manipulation-robot/arm/arm_controller.py
    arm_controller = ExecuteProcess(
        cmd=['python3', f'{project_root}/arm/arm_controller.py'],
        output='screen',
        name='arm_controller',
        condition=IfCondition(LaunchConfiguration('start_arm_controller')),
    )

    # 2. 交通灯检测 | 命令行: python3 /home/tony/ros2_ws/src/mobile-manipulation-robot/detection/inference_nuc.py
    traffic_light_detection = ExecuteProcess(
        cmd=[
            'python3', f'{project_root}/detection/inference_nuc.py',
            '--ros-args',
            '-p', ['model_path:=', traffic_model_path],
            '-p', ['image_topic:=', traffic_image_topic],
            '-p', ['device:=', traffic_device],
            '-p', ['conf_threshold:=', traffic_conf_threshold],
            '-p', ['filter_window_size:=', traffic_filter_window_size],
            '-p', ['stop_threshold:=', traffic_stop_threshold],
        ],
        output='screen',
        name='traffic_light_detection',
        condition=IfCondition(LaunchConfiguration('start_traffic_detection')),
    )

    # 3. 抓取脚本(可选) | 命令行: python3 /home/tony/ros2_ws/src/mobile-manipulation-robot/arm/grasping_ok.py
    grasping_ok = ExecuteProcess(
        cmd=[
            'python3', f'{project_root}/arm/grasping_ok.py',
            '--ros-args',
            '-p', ['vision_mode:=', grasp_vision_mode],
            '-p', ['allow_fixed_fallback:=', allow_fixed_fallback],
            '-p', ['fixed_target_x:=', fixed_target_x],
            '-p', ['fixed_target_y:=', fixed_target_y],
            '-p', ['fixed_target_z:=', fixed_target_z],
            '-p', ['grasp_verification:=', grasp_verification],
            '-p', ['gripper_state_topic:=', gripper_state_topic],
            '-p', ['search_timeout_sec:=', grasp_search_timeout_sec],
            '-p', ['target_stability_tolerance:=', target_stability_tolerance],
            '-p', ['target_stability_frames:=', target_stability_frames],
            '-p', ['pan_tilt_pitch_deg:=', pan_tilt_pitch_deg],
            '-p', ['pan_tilt_settle_sec:=', pan_tilt_settle_sec],
            '-p', ['detector_startup_sec:=', detector_startup_sec],
            '-p', ['max_ik_retries:=', max_ik_retries],
            '-p', ['gripper_object_gap:=', gripper_object_gap],
            '-p', ['gripper_open_position:=', gripper_open_position],
            '-p', ['gripper_close_position:=', gripper_close_position],
            '-p', ['grasp_verification_timeout_sec:=', grasp_verification_timeout_sec],
        ],
        output='screen',
        name='grasping_ok',
        condition=IfCondition(LaunchConfiguration('start_grasping')),
    )

    # 4. 放置盒子脚本(可选) | 命令行: python3 /home/tony/ros2_ws/src/mobile-manipulation-robot/arm/place_the_box.py
    place_box = ExecuteProcess(
        cmd=[
            'python3', f'{project_root}/arm/place_the_box.py',
            '--ros-args',
            '-p', ['place_verification:=', place_verification],
            '-p', ['gripper_state_topic:=', gripper_state_topic],
            '-p', ['gripper_open_position:=', gripper_open_position],
            '-p', ['place_open_tolerance:=', place_open_tolerance],
            '-p', ['place_verification_timeout_sec:=', place_verification_timeout_sec],
        ],
        output='screen',
        name='place_box',
        condition=IfCondition(LaunchConfiguration('start_placing')),
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false', description='Use simulation time if true'),
        DeclareLaunchArgument('start_arm_controller', default_value='true'),
        DeclareLaunchArgument('start_traffic_detection', default_value='true'),
        DeclareLaunchArgument('start_grasping', default_value='true'),
        DeclareLaunchArgument('start_placing', default_value='true'),
        DeclareLaunchArgument(
            'grasp_vision_mode',
            default_value='aruco',
            description='aruco, box, or auto for marker-free fallback localization',
        ),
        DeclareLaunchArgument(
            'allow_fixed_fallback',
            default_value='false',
            description='Use the calibrated fixed target if visual search times out',
        ),
        DeclareLaunchArgument('fixed_target_x', default_value='0.20'),
        DeclareLaunchArgument('fixed_target_y', default_value='0.0'),
        DeclareLaunchArgument('fixed_target_z', default_value='0.05'),
        DeclareLaunchArgument('gripper_state_topic', default_value='/joint_states'),
        DeclareLaunchArgument('grasp_search_timeout_sec', default_value='15.0'),
        DeclareLaunchArgument('target_stability_tolerance', default_value='0.02'),
        DeclareLaunchArgument('target_stability_frames', default_value='6'),
        DeclareLaunchArgument('pan_tilt_pitch_deg', default_value='37.0'),
        DeclareLaunchArgument('pan_tilt_settle_sec', default_value='5.0'),
        DeclareLaunchArgument('detector_startup_sec', default_value='2.0'),
        DeclareLaunchArgument('max_ik_retries', default_value='2'),
        DeclareLaunchArgument('gripper_object_gap', default_value='0.05'),
        DeclareLaunchArgument('gripper_open_position', default_value='1.57'),
        DeclareLaunchArgument('gripper_close_position', default_value='0.62'),
        DeclareLaunchArgument('grasp_verification_timeout_sec', default_value='3.0'),
        DeclareLaunchArgument(
            'place_verification',
            default_value='commanded',
            description='commanded preserves legacy behavior; joint_state verifies gripper opening',
        ),
        DeclareLaunchArgument('place_open_tolerance', default_value='0.10'),
        DeclareLaunchArgument('place_verification_timeout_sec', default_value='3.0'),
        DeclareLaunchArgument(
            'grasp_verification',
            default_value='commanded',
            description='commanded keeps legacy behavior; joint_state enables gripper-position heuristic',
        ),
        DeclareLaunchArgument(
            'traffic_model_path',
            default_value=f'{project_root}/detection/best_openvino_model',
        ),
        DeclareLaunchArgument(
            'traffic_image_topic',
            default_value='/camera/camera/color/image_raw',
        ),
        DeclareLaunchArgument('traffic_device', default_value='CPU'),
        DeclareLaunchArgument('traffic_conf_threshold', default_value='0.5'),
        DeclareLaunchArgument('traffic_filter_window_size', default_value='5'),
        DeclareLaunchArgument('traffic_stop_threshold', default_value='70'),
        arm_controller,         # 机械臂控制
        traffic_light_detection,# 交通灯检测
        grasping_ok,            # 抓取(可选，不需要直接删此行)
        place_box               # 放置盒子(可选，不需要直接删此行)
    ])

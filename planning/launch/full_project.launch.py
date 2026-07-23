#!/usr/bin/env python3
"""Single entry point for the complete mobile robot application mission.

The vendor robot bringup remains external and untouched.  This launch file
starts the application-side camera/pan-tilt drivers (optionally), traffic
detection, arm task nodes, Nav2 localization/navigation, and the mission
state machine in one command.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    project_root = "/home/tony/ros2_ws/src/mobile-manipulation-robot"
    planning_share = get_package_share_directory("planning")

    start_camera = LaunchConfiguration("start_camera")
    start_pan_tilt = LaunchConfiguration("start_pan_tilt")

    camera_share = get_package_share_directory("realsense2_camera")
    camera = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(camera_share, "launch", "rs_launch.py")
        ),
        launch_arguments={
            "enable_color": "true",
            "enable_depth": "true",
            "publish_tf": "true",
        }.items(),
        condition=IfCondition(start_camera),
    )

    pan_tilt_share = get_package_share_directory("pan_tilt_bringup")
    pan_tilt = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pan_tilt_share, "launch", "panTilt_bringup.launch.py")
        ),
        condition=IfCondition(start_pan_tilt),
    )

    supplement = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(project_root, "planning", "launch", "supplement.launch.py")
        ),
        launch_arguments={
            "start_arm_controller": LaunchConfiguration("start_arm_controller"),
            "start_traffic_detection": LaunchConfiguration("start_traffic_detection"),
            "start_grasping": LaunchConfiguration("start_grasping"),
            "start_placing": LaunchConfiguration("start_placing"),
            "grasp_vision_mode": LaunchConfiguration("grasp_vision_mode"),
            "allow_fixed_fallback": LaunchConfiguration("allow_fixed_fallback"),
            "fixed_target_x": LaunchConfiguration("fixed_target_x"),
            "fixed_target_y": LaunchConfiguration("fixed_target_y"),
            "fixed_target_z": LaunchConfiguration("fixed_target_z"),
            "grasp_verification": LaunchConfiguration("grasp_verification"),
            "gripper_state_topic": LaunchConfiguration("gripper_state_topic"),
            "grasp_search_timeout_sec": LaunchConfiguration("grasp_search_timeout_sec"),
            "target_stability_tolerance": LaunchConfiguration("target_stability_tolerance"),
            "target_stability_frames": LaunchConfiguration("target_stability_frames"),
            "pan_tilt_pitch_deg": LaunchConfiguration("pan_tilt_pitch_deg"),
            "pan_tilt_settle_sec": LaunchConfiguration("pan_tilt_settle_sec"),
            "detector_startup_sec": LaunchConfiguration("detector_startup_sec"),
            "max_ik_retries": LaunchConfiguration("max_ik_retries"),
            "gripper_object_gap": LaunchConfiguration("gripper_object_gap"),
            "gripper_open_position": LaunchConfiguration("gripper_open_position"),
            "gripper_close_position": LaunchConfiguration("gripper_close_position"),
            "grasp_verification_timeout_sec": LaunchConfiguration(
                "grasp_verification_timeout_sec"
            ),
            "place_verification": LaunchConfiguration("place_verification"),
            "place_open_tolerance": LaunchConfiguration("place_open_tolerance"),
            "place_verification_timeout_sec": LaunchConfiguration(
                "place_verification_timeout_sec"
            ),
            "traffic_model_path": LaunchConfiguration("traffic_model_path"),
            "traffic_image_topic": LaunchConfiguration("traffic_image_topic"),
            "traffic_device": LaunchConfiguration("traffic_device"),
            "traffic_conf_threshold": LaunchConfiguration("traffic_conf_threshold"),
            "traffic_filter_window_size": LaunchConfiguration(
                "traffic_filter_window_size"
            ),
            "traffic_stop_threshold": LaunchConfiguration("traffic_stop_threshold"),
        }.items(),
    )

    navigation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(planning_share, "launch", "navigation_full.launch.py")
        ),
        launch_arguments={
            "params_file": LaunchConfiguration("params_file"),
            "navigation_retry_limit": LaunchConfiguration("navigation_retry_limit"),
            "navigation_timeout_sec": LaunchConfiguration("navigation_timeout_sec"),
            "grasp_timeout_sec": LaunchConfiguration("grasp_timeout_sec"),
            "place_timeout_sec": LaunchConfiguration("place_timeout_sec"),
        }.items(),
    )

    arguments = [
        DeclareLaunchArgument("start_arm_controller", default_value="true"),
        DeclareLaunchArgument("start_traffic_detection", default_value="true"),
        DeclareLaunchArgument("start_grasping", default_value="true"),
        DeclareLaunchArgument("start_placing", default_value="true"),
        DeclareLaunchArgument(
            "start_camera",
            default_value="true",
            description="Start the RealSense driver; set false if already running",
        ),
        DeclareLaunchArgument(
            "start_pan_tilt",
            default_value="true",
            description="Start the pan-tilt driver; set false if already running",
        ),
        DeclareLaunchArgument(
            "grasp_vision_mode",
            default_value="aruco",
            description="aruco, box, or auto for marker-free fallback localization",
        ),
        DeclareLaunchArgument("allow_fixed_fallback", default_value="false"),
        DeclareLaunchArgument("fixed_target_x", default_value="0.20"),
        DeclareLaunchArgument("fixed_target_y", default_value="0.0"),
        DeclareLaunchArgument("fixed_target_z", default_value="0.05"),
        DeclareLaunchArgument("grasp_verification", default_value="commanded"),
        DeclareLaunchArgument("gripper_state_topic", default_value="/joint_states"),
        DeclareLaunchArgument("grasp_search_timeout_sec", default_value="15.0"),
        DeclareLaunchArgument("target_stability_tolerance", default_value="0.02"),
        DeclareLaunchArgument("target_stability_frames", default_value="6"),
        DeclareLaunchArgument("pan_tilt_pitch_deg", default_value="37.0"),
        DeclareLaunchArgument("pan_tilt_settle_sec", default_value="5.0"),
        DeclareLaunchArgument("detector_startup_sec", default_value="2.0"),
        DeclareLaunchArgument("max_ik_retries", default_value="2"),
        DeclareLaunchArgument("gripper_object_gap", default_value="0.05"),
        DeclareLaunchArgument("gripper_open_position", default_value="1.57"),
        DeclareLaunchArgument("gripper_close_position", default_value="0.62"),
        DeclareLaunchArgument("grasp_verification_timeout_sec", default_value="3.0"),
        DeclareLaunchArgument("place_verification", default_value="commanded"),
        DeclareLaunchArgument("place_open_tolerance", default_value="0.10"),
        DeclareLaunchArgument("place_verification_timeout_sec", default_value="3.0"),
        DeclareLaunchArgument(
            "traffic_model_path",
            default_value=f"{project_root}/detection/best_openvino_model",
        ),
        DeclareLaunchArgument(
            "traffic_image_topic",
            default_value="/camera/camera/color/image_raw",
        ),
        DeclareLaunchArgument("traffic_device", default_value="CPU"),
        DeclareLaunchArgument("traffic_conf_threshold", default_value="0.5"),
        DeclareLaunchArgument("traffic_filter_window_size", default_value="5"),
        DeclareLaunchArgument("traffic_stop_threshold", default_value="70"),
        DeclareLaunchArgument(
            "params_file",
            default_value=os.path.join(
                get_package_share_directory("iqr_tb4_navigation"),
                "config",
                "nav2.yaml",
            ),
        ),
        DeclareLaunchArgument("navigation_retry_limit", default_value="2"),
        DeclareLaunchArgument("navigation_timeout_sec", default_value="180.0"),
        DeclareLaunchArgument("grasp_timeout_sec", default_value="120.0"),
        DeclareLaunchArgument("place_timeout_sec", default_value="60.0"),
    ]

    return LaunchDescription(arguments + [camera, pan_tilt, supplement, navigation])

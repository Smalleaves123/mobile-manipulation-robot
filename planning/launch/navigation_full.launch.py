import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    project_root = "/home/tony/ros2_ws/src/mobile-manipulation-robot"
    map_path = f"{project_root}/planning/map/map.yaml"
    navigation_share = get_package_share_directory("iqr_tb4_navigation")
    nav2_params = LaunchConfiguration("params_file")
    navigation_retry_limit = LaunchConfiguration("navigation_retry_limit")
    navigation_timeout_sec = LaunchConfiguration("navigation_timeout_sec")
    grasp_timeout_sec = LaunchConfiguration("grasp_timeout_sec")
    place_timeout_sec = LaunchConfiguration("place_timeout_sec")

    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(navigation_share, "launch", "localization.launch.py")
        ),
        launch_arguments={"map": map_path}.items(),
    )
    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(navigation_share, "launch", "nav2.launch.py")
        ),
        launch_arguments={
            "params_file": nav2_params,
            "use_sim_time": "false",
        }.items(),
    )
    mission = TimerAction(
        period=3.0,
        actions=[
            Node(
                package="planning",
                executable="navigation_full",
                output="screen",
                parameters=[
                    {
                        "navigation_retry_limit": navigation_retry_limit,
                        "navigation_timeout_sec": navigation_timeout_sec,
                        "grasp_timeout_sec": grasp_timeout_sec,
                        "place_timeout_sec": place_timeout_sec,
                    }
                ],
            )
        ],
    )
    return LaunchDescription([
        DeclareLaunchArgument(
            "params_file",
            default_value=PathJoinSubstitution([
                navigation_share,
                "config",
                "nav2.yaml",
            ]),
            description="Nav2 parameter file; pass a merged file to enable MyAStarPlanner",
        ),
        DeclareLaunchArgument("navigation_retry_limit", default_value="2"),
        DeclareLaunchArgument("navigation_timeout_sec", default_value="180.0"),
        DeclareLaunchArgument("grasp_timeout_sec", default_value="120.0"),
        DeclareLaunchArgument("place_timeout_sec", default_value="60.0"),
        localization,
        nav2,
        mission,
    ])

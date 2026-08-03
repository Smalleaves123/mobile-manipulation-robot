# Author: Addison Sears-Collins
# Date: September 14, 2021
# Description: Launch a two-wheeled robot URDF file using Rviz.
# https://automaticaddison.com

import os
import time
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch .actions import TimerAction


def generate_launch_description():

  # Set the path to this package.
  pkg_share = FindPackageShare(package='iqr_tb4_description').find('iqr_tb4_description')
  iqr_tb4_share = FindPackageShare(package='iqr_tb4_bringup').find('iqr_tb4_bringup')
  witmotion_share = FindPackageShare(package='witmotion_ros_driver').find('witmotion_ros_driver')
  rplidar_share = FindPackageShare(package='rplidar_ros').find('rplidar_ros')
  # pan_tilt_share = FindPackageShare(package='pan_tilt_bringup').find('pan_tilt_bringup')
  # realsense_share = FindPackageShare(package='realsense2_camera').find('realsense2_camera')

  # Set the path to the RViz configuration settings
  default_rviz_config_path = os.path.join(pkg_share, 'rviz/rviz_basic_settings.rviz')
  arm_bringup_path = os.path.join(iqr_tb4_share, 'launch/arm_bringup.launch.py')
  imu_bringup_path = os.path.join(witmotion_share, 'launch/modbus_rtu_driver.launch.py')
  imu2_bringup_path = os.path.join(witmotion_share, 'launch/serial_bridge.launch.py')
  rplidar_bringup_path = os.path.join(rplidar_share, 'launch/rplidar_a2m7_launch.py')
  # realsense_bringup_path = os.path.join(realsense_share, 'launch/rs_launch.py')
  # pan_tilt_bringup_path = os.path.join(pan_tilt_share, 'launch/panTilt_bringup.launch.py')

  # Set the path to the URDF file
  default_urdf_model_path = os.path.join(pkg_share, 'urdf/tb_full.urdf.xacro')

  ########### YOU DO NOT NEED TO CHANGE ANYTHING BELOW THIS LINE ##############  
  # Launch configuration variables specific to simulation
  gui = LaunchConfiguration('gui')
  urdf_model = LaunchConfiguration('urdf_model')
  rviz_config_file = LaunchConfiguration('rviz_config_file')
  use_robot_state_pub = LaunchConfiguration('use_robot_state_pub')
  bringup_use_rviz = LaunchConfiguration('bringup_use_rviz')
  use_sim_time = LaunchConfiguration('use_sim_time')

  # Declare the launch arguments  
  declare_urdf_model_path_cmd = DeclareLaunchArgument(
    name='urdf_model', 
    default_value=default_urdf_model_path, 
    description='Absolute path to robot urdf file')
 
  declare_rviz_config_file_cmd = DeclareLaunchArgument(
    name='rviz_config_file',
    default_value=default_rviz_config_path,
    description='Full path to the RVIZ config file to use')
 
  declare_use_joint_state_publisher_cmd = DeclareLaunchArgument(
    name='gui',
    default_value='false',
    description='Flag to enable joint_state_publisher_gui')
 
  declare_use_robot_state_pub_cmd = DeclareLaunchArgument(
    name='use_robot_state_pub',
    default_value='true',
    description='Whether to start the robot state publisher')

  declare_use_rviz_cmd = DeclareLaunchArgument(
    name='bringup_use_rviz',
    default_value='True',
    description='Whether to start RVIZ')
 
  declare_use_sim_time_cmd = DeclareLaunchArgument(
    name='use_sim_time',
    default_value='false',
    description='Use simulation (Gazebo) clock if true')
 
  declare_arm_robot_model_cmd = DeclareLaunchArgument(
    name='robot_model',
    default_value='px100',
    description='arm model')


  # Specify the actions

  # Publish the joint state values for the non-fixed joints in the URDF file.
  # start_joint_state_publisher_cmd = Node(
  #   condition=IfCondition(gui),
  #   package='joint_state_publisher',
  #   executable='joint_state_publisher',
  #   name='joint_state_publisher',
  #   remappings=[
  #     ('/tf', 'tf'),
  #     ('/tf_static', 'tf_static')
  #   ]
  # )

  # # A GUI to manipulate the joint state values
  # start_joint_state_publisher_gui_node = Node(
  #   condition=IfCondition(gui),
  #   package='joint_state_publisher_gui',
  #   executable='joint_state_publisher_gui',
  #   name='joint_state_publisher_gui')

  # Subscribe to the joint states of the robot, and publish the 3D pose of each link.
  start_robot_state_publisher_cmd = Node(
    condition=IfCondition(use_robot_state_pub),
    package='robot_state_publisher',
    executable='robot_state_publisher',
    parameters=[{'use_sim_time': use_sim_time, 
    'robot_description': Command(['xacro ', urdf_model])}],
    arguments=[default_urdf_model_path],
    remappings=[
      ('/tf', 'tf'),
      ('/tf_static', 'tf_static')
    ]
  )

  left_wheel_drop_stf = Node(
    name='left_wheel_drop_stf',
    package='tf2_ros',
    executable='static_transform_publisher',
    output='screen',
    arguments=[
      '--x', '0.0',
      '--y', '0.1165',
      '--z', '0.0402',
      '--roll', '-1.5707',
      '--pitch', '0.0',
      '--yaw', '0.0',
      '--frame-id', 'base_link',
      '--child-frame-id', 'wheel_drop_left',
    ],
    remappings=[
      ('/tf_static', 'tf_static')
    ],
  )

  right_wheel_drop_stf = Node(
    name='right_wheel_drop_stf',
    package='tf2_ros',
    executable='static_transform_publisher',
    output='screen',
    arguments=[
        '--x', '0.0',
        '--y', '-0.1165',
        '--z', '0.0402',
        '--roll', '-1.5707',
        '--pitch', '0.0',
        '--yaw', '0.0',
        '--frame-id', 'base_link',
        '--child-frame-id', 'wheel_drop_right',
    ],
    remappings=[
        ('/tf_static', 'tf_static')
    ],
  )

  # Launch RViz
  start_rviz_cmd = Node(
    condition=IfCondition(bringup_use_rviz),
    package='rviz2',
    executable='rviz2',
    name='rviz2',
    output='screen',
    arguments=['-d', rviz_config_file])
 
  # odom tf repub
  # start_odom_tf_cmd = Node(
  #   package='iqr_tb4_bringup',
  #   executable='odom_tf_reboard.py',
  #   name='odom_tf_reboard',
  #   output='screen'
  # )

  # arm bringup
  robot_model = LaunchConfiguration('robot_model')
  arm_bringup = IncludeLaunchDescription(
    PythonLaunchDescriptionSource([arm_bringup_path]),
    launch_arguments={'robot_model': robot_model, 'robot_name': 'px100'}.items()
  )

  # imu bringup
  imu2_bringup = IncludeLaunchDescription(
    PythonLaunchDescriptionSource([imu2_bringup_path])
  )
  imu_bringup = IncludeLaunchDescription(
    PythonLaunchDescriptionSource([imu_bringup_path])
  )

  # rplidar bringup
  rplidar_bringup = IncludeLaunchDescription(
    PythonLaunchDescriptionSource([rplidar_bringup_path]),
    launch_arguments={'serial_port': '/dev/rplidar', 'serial_baudrate': '115200', 'frame_id': 'laser_link', 'inverted': 'false'}.items()
  )

  # realsense bringup
  # realsense_bringup = IncludeLaunchDescription(
  #   PythonLaunchDescriptionSource([realsense_bringup_path]),
  #   launch_arguments={'pointcloud.enable': 'true', 'publish_tf': 'true'}.items()
  # )

  # # pan tilt bringup
  # pan_tilt_bringup = IncludeLaunchDescription(
  #   PythonLaunchDescriptionSource([pan_tilt_bringup_path])
  # )
  

  # Create the launch description and populate
  ld = LaunchDescription()

  # Declare the launch options

  ld.add_action(declare_urdf_model_path_cmd)
  ld.add_action(declare_rviz_config_file_cmd)
  ld.add_action(declare_use_joint_state_publisher_cmd)
  ld.add_action(declare_use_robot_state_pub_cmd)  
  ld.add_action(declare_use_rviz_cmd) 
  ld.add_action(declare_use_sim_time_cmd)
  ld.add_action(declare_arm_robot_model_cmd)

  # Add any actions
  ld.add_action(arm_bringup)
  # ld.add_action(start_joint_state_publisher_cmd)
  # ld.add_action(start_joint_state_publisher_gui_node)
  ld.add_action(start_robot_state_publisher_cmd)
  # ld.add_action(start_odom_tf_cmd)
  ld.add_action(imu2_bringup)
  ld.add_action(imu_bringup)
  ld.add_action(rplidar_bringup)
  # ld.add_action(pan_tilt_bringup)
  # ld.add_action(realsense_bringup)
  ld.add_action(left_wheel_drop_stf)
  ld.add_action(right_wheel_drop_stf)


  # timer_action = TimerAction(period=2.0, actions=[start_rviz_cmd])
  # ld.add_action(timer_action)

  return ld

# WitMotion IMU ROS2 Driver

目前该ROS2包仅包含适用于HWT6052-485的驱动。

原理为使用serial-driver提供的串口收发Topic，通过`serial_write`Topic发送modbus请求，然后通过`serial_read`获取串口返回的结果，并根据ModbusID，数据帧长度来对不同的modbus请求进行区分，进而获取到想要的数据。

## Known Issues

- 在串口波特率为115200的情况下，帧率最快为25Hz，原因未知。

## Howto

1. Clone source to your ros2 workspace

    ```bash
    mkdir -p ~/ros2_ws/src
    cd ~/ros2_ws/src
    git clone https://e.coding.net/iqr/sensor/witmotion_ros_driver.git
    ```

2. Build

    ```bash
    cd ~/ros2_ws
    colcon build --symlink-install
    ```

3. Use

    ```bash
    # 串口转发节点
    ros2 launch witmotion_ros_driver serial_bridge.launch.py

    # ModbusRTU协议的IMU的节点
    ros2 launch witmotion_ros_driver modbus_rtu_driver.launch.py
    ```

## Param

- config/params.yaml
    - 用途：该文件为串口和IMU驱动的配置参数文件

## Nodes

### modbus_rtu_driver

ModbusRTU协议的IMU驱动程序

#### Params

- id:
    - 说明：IMU的ID值
    - 默认值：0x50
- frame_link:
    - 说明：IMU所处的Link的名称
    - 默认值：external_imu_link

#### Topic

- /external_imu:
    - 类型：sensor_msgs.msg.Imu
    - 用途：包含加速度，角速度和位姿四元数

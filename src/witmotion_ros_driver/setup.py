import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'witmotion_ros_driver'

setup(
    name=package_name,
    version='1.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob(os.path.join('config', '*'))),
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*launch.[pxy][yma]*')))
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Ian Tian',
    maintainer_email='ye.tian@iqr-robot.com',
    description='Witmotion IMU ROS2 Driver',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'modbus_rtu_driver=' + package_name + '.modbus_rtu_driver:main',
            'modbus_rtu_driver_2=' + package_name + '.modbus_rtu_driver_2:main'
        ],
    },
)

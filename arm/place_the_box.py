#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
import math

from interbotix_xs_msgs.msg import JointGroupCommand, JointSingleCommand
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, String

class PlaceBoxNode(Node):
    def __init__(self):
        super().__init__('place_box_node')
        # Publishers
        self.pub_arm = self.create_publisher(JointGroupCommand, '/px100/commands/joint_group', 10)
        self.pub_gripper = self.create_publisher(JointSingleCommand, '/px100/commands/joint_single', 10)
        self.pub_place_success = self.create_publisher(Bool, '/place/success', 10)
        self.pub_place_status = self.create_publisher(String, '/place/status', 10)

        self.declare_parameter('place_verification', 'commanded')
        self.declare_parameter('gripper_state_topic', '/joint_states')
        self.declare_parameter('gripper_open_position', 1.57)
        self.declare_parameter('place_open_tolerance', 0.10)
        self.declare_parameter('place_verification_timeout_sec', 3.0)
        self.place_verification = str(
            self.get_parameter('place_verification').value
        ).lower()
        if self.place_verification not in {'commanded', 'joint_state'}:
            self.get_logger().warn(
                '未知 place_verification=%s，回退到 commanded',
                self.place_verification,
            )
            self.place_verification = 'commanded'
        self.gripper_state_topic = str(
            self.get_parameter('gripper_state_topic').value
        )
        self.gripper_open_position = float(
            self.get_parameter('gripper_open_position').value
        )
        self.place_open_tolerance = max(
            0.0, float(self.get_parameter('place_open_tolerance').value)
        )
        self.verification_ticks_limit = max(
            1,
            math.ceil(
                float(self.get_parameter('place_verification_timeout_sec').value)
                / 0.5
            ),
        )

        # 订阅启动话题
        self.sub_start = self.create_subscription(Bool, '/place/start', self.cb_start, 10)
        self.sub_joint_states = self.create_subscription(
            JointState,
            self.gripper_state_topic,
            self.cb_joint_states,
            10,
        )

        # 等待启动信号
        self.started = False
        # Simple state machine
        self.state = 'WAITING_START'
        self.wait_ticks = 2  # give some time for publishers to connect
        self.verify_ticks = 0
        self.gripper_position = None
        self.failure_reason = ''

        # Timer
        self.timer = self.create_timer(0.5, self.loop)
        self.get_logger().info('✅ 节点启动: 等待 /place/start 话题中的 True 指令...')
        self._publish_status('WAITING_START', '等待 /place/start')

    def cb_start(self, msg: Bool):
        """接收启动信号"""
        if msg.data and not self.started:
            self.get_logger().info('🚀 收到启动信号，开始执行放置任务...')
            self.started = True
            self.failure_reason = ''
            self.verify_ticks = 0
            self.gripper_position = None
            # 切换到执行状态
            self.state = 'MOVE_OUT'
            self.wait_ticks = 2

    def send_arm(self, joints):
        msg = JointGroupCommand()
        msg.name = 'arm'
        msg.cmd = joints
        self.pub_arm.publish(msg)

    def send_gripper(self, val):
        msg = JointSingleCommand()
        msg.name = 'gripper'
        msg.cmd = float(val)
        self.pub_gripper.publish(msg)

    def cb_joint_states(self, msg: JointState):
        """Cache a gripper position for optional release verification."""
        index = None
        for name in ('gripper', 'gripper_joint', 'left_finger_joint'):
            if name in msg.name:
                index = msg.name.index(name)
                break
        if index is not None and index < len(msg.position):
            self.gripper_position = float(msg.position[index])

    def _publish_status(self, status: str, detail: str) -> None:
        self.pub_place_status.publish(String(data=f'{status}: {detail}'))

    def _publish_result(self, success: bool, detail: str) -> None:
        self.pub_place_success.publish(Bool(data=bool(success)))
        self._publish_status('SUCCEEDED' if success else 'FAILED', detail)
        self.get_logger().info(
            '放置结果已发布: %s (%s)', 'success' if success else 'failed', detail
        )

    def _fail(self, reason: str) -> None:
        self.failure_reason = reason
        self.get_logger().error('❌ 放置失败: %s', reason)
        self._publish_status('FAILED', reason)
        self.state = 'FAILED'

    def loop(self):
        if self.wait_ticks > 0:
            self.wait_ticks -= 1
            return

        if self.state == 'WAITING_START':
            # 等待启动信号，不执行任何操作
            pass

        elif self.state == 'MOVE_OUT':
            # A safe forward "place" pose; gripper level (shoulder+elbow+wrist≈0)
            # [waist, shoulder, elbow, wrist]
            place_pose = [-1.57, -0.4, 1.1, -0.7]
            self.get_logger().info('Extending arm to place pose...')
            self.send_arm(place_pose)
            self.state = 'OPEN'
            self.wait_ticks = 6  # wait ~3s for the arm to reach
            self._publish_status('MOVE_OUT', '机械臂移动到放置位')

        elif self.state == 'OPEN':
            self.get_logger().info('Opening gripper to release object...')
            self.send_gripper(self.gripper_open_position)
            if self.place_verification == 'joint_state':
                self.state = 'VERIFY_OPEN'
                self.verify_ticks = 0
                self._publish_status('VERIFYING', '等待夹爪打开状态')
            else:
                # Compatibility mode preserves the original commanded-success
                # behavior when no usable gripper feedback is available.
                self.state = 'DONE'
            self.wait_ticks = 4  # short wait then exit

        elif self.state == 'VERIFY_OPEN':
            self.verify_ticks += 1
            if self.gripper_position is not None:
                opened = self.gripper_position >= (
                    self.gripper_open_position - self.place_open_tolerance
                )
                if opened:
                    self.state = 'DONE'
                    self.wait_ticks = 1
                elif self.verify_ticks >= self.verification_ticks_limit:
                    self._fail('夹爪未达到打开位置，放置状态无法确认')
            elif self.verify_ticks >= self.verification_ticks_limit:
                self._fail('未收到夹爪关节状态，无法完成放置核验')

        elif self.state == 'DONE':
            self.get_logger().info('Done. Publishing placement result...')
            self._publish_result(True, '夹爪已打开，物块已释放' if self.place_verification == 'joint_state' else '执行放置指令完成')
            # 成功信号只发布一次，避免导航节点重复推进或重复执行。
            self.state = 'FINISHED'

        elif self.state == 'FAILED':
            self.send_arm([1.57, -0.3, 1.57, -1.3])
            self._publish_result(False, self.failure_reason or '放置未通过核验')
            self.state = 'FINISHED'

        elif self.state == 'FINISHED':
            pass


def main():
    rclpy.init()
    node = PlaceBoxNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()

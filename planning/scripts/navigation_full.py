#!/usr/bin/env python3
"""Complete mobile-manipulation mission adapter for the robot's Nav2 installation.

The original ``navigation.py`` remains available as the stable fixed-route
fallback.  This node adds the full task handshake around the same Nav2 action:

1. navigate through the configured map waypoints;
2. trigger grasping at waypoint 4 and wait for ``/grasp/success``;
3. trigger placing at waypoint 5 and wait for ``/place/success``;
4. finish at the final waypoint.

Traffic-light stop messages cancel the active goal and resume the same goal
after the stop signal clears.  No ROS-independent package is required; all
mission state is kept here so this file can be copied directly to the robot.
"""

import time

import rclpy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from action_msgs.msg import GoalStatus
from std_msgs.msg import Bool, String


class FullMissionNavigator(Node):
    """ROS2 state machine for navigation, grasping and placing."""

    def __init__(self) -> None:
        super().__init__("full_mission_navigator")

        self.declare_parameter("navigation_retry_limit", 2)
        self.declare_parameter("navigation_timeout_sec", 180.0)
        self.declare_parameter("grasp_timeout_sec", 120.0)
        self.declare_parameter("place_timeout_sec", 60.0)
        self.navigation_retry_limit = max(
            0, int(self.get_parameter("navigation_retry_limit").value)
        )
        self.navigation_timeout_sec = max(
            10.0, float(self.get_parameter("navigation_timeout_sec").value)
        )
        self.grasp_timeout_sec = max(
            1.0, float(self.get_parameter("grasp_timeout_sec").value)
        )
        self.place_timeout_sec = max(
            1.0, float(self.get_parameter("place_timeout_sec").value)
        )

        self.action_client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self.init_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, "/initialpose", 1
        )
        self.grasp_start_pub = self.create_publisher(Bool, "/grasp/start", 10)
        self.place_start_pub = self.create_publisher(Bool, "/place/start", 10)
        self.mission_status_pub = self.create_publisher(String, "/mission/status", 10)
        self.mission_success_pub = self.create_publisher(Bool, "/mission/success", 10)

        self.grasp_sub = self.create_subscription(
            Bool, "/grasp/success", self._grasp_callback, 10
        )
        self.place_sub = self.create_subscription(
            Bool, "/place/success", self._place_callback, 10
        )
        self.stop_sub = self.create_subscription(
            Bool, "/traffic_light/stop_control", self._traffic_callback, 10
        )

        # Preserve the route already used on the physical robot.  Each tuple
        # is x, y, quaternion.z, quaternion.w in the map frame.
        self.waypoints = self._default_waypoints()
        self.current_goal_idx = 0
        self.navigation_retries = 0

        self.goal_handle = None
        self.goal_in_progress = False
        self.goal_sequence = 0
        self.active_goal_sequence = None
        # A goal may be cancelled before Nav2 returns its goal handle.
        # Remember those sequences so a late response is cancelled too.
        self.cancelled_goal_sequences: set[int] = set()
        self.initial_pose_sent = False
        self.state = "IDLE"
        self.state_before_stop = None
        self.navigation_deadline = None
        self.task_deadline = None
        self.watchdog_timer = self.create_timer(1.0, self._watchdog_callback)
        self._publish_mission_status("IDLE", "等待开始")

    @staticmethod
    def _default_waypoints() -> list[tuple[float, float, float, float]]:
        return [
            (6.7132, -2.0496, -0.483441, 0.875377),
            (6.7167, -3.2733, -0.351566, 0.936163),
            (8.7445, -4.2035, 0.381371, 0.924422),
            (11.1434, -2.4972, -0.212324, 0.954916),
            (9.0319, -0.5364, -0.998852, 0.047912),
            (6.7132, -2.0496, -0.483441, 0.875377),
        ]

    def start(self) -> None:
        """Publish the initial AMCL pose and start the first navigation goal."""
        self._send_current_goal()

    def _publish_initial_pose(self) -> None:
        if self.initial_pose_sent:
            return

        x, y, yaw_z, yaw_w = self.waypoints[0]
        message = PoseWithCovarianceStamped()
        message.header.frame_id = "map"
        message.pose.pose.position.x = x
        message.pose.pose.position.y = y
        message.pose.pose.orientation.z = yaw_z
        message.pose.pose.orientation.w = yaw_w
        message.pose.covariance[0] = 0.25
        message.pose.covariance[7] = 0.25
        message.pose.covariance[35] = 0.068

        # AMCL may not receive a single latched message during startup, so
        # retain the original project's repeated publication behavior.
        for _ in range(5):
            message.header.stamp = self.get_clock().now().to_msg()
            self.init_pose_pub.publish(message)
            time.sleep(0.2)
        self.initial_pose_sent = True

    def _send_current_goal(self) -> None:
        if self.state in {"TRAFFIC_STOPPED", "WAITING_GRASP", "WAITING_PLACE", "DONE"}:
            return
        if self.goal_in_progress:
            return
        if self.current_goal_idx >= len(self.waypoints):
            self._complete_mission()
            return

        if not self.action_client.wait_for_server(timeout_sec=10.0):
            self._handle_navigation_failure("NavigateToPose action server unavailable")
            return

        self._publish_initial_pose()
        x, y, yaw_z, yaw_w = self.waypoints[self.current_goal_idx]
        pose = PoseStamped()
        pose.header.frame_id = "map"
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.orientation.z = yaw_z
        pose.pose.orientation.w = yaw_w

        goal = NavigateToPose.Goal()
        goal.pose = pose
        self.state = "NAVIGATING"
        self.goal_in_progress = True
        self.navigation_deadline = time.monotonic() + self.navigation_timeout_sec
        self.goal_sequence += 1
        goal_sequence = self.goal_sequence
        self.active_goal_sequence = goal_sequence
        self.get_logger().info(
            "发送导航目标 %d/%d: x=%.3f y=%.3f",
            self.current_goal_idx + 1,
            len(self.waypoints),
            x,
            y,
        )
        future = self.action_client.send_goal_async(goal)
        future.add_done_callback(
            lambda result_future: self._goal_response_callback(
                result_future, goal_sequence
            )
        )

    def _goal_response_callback(self, future, goal_sequence) -> None:
        if goal_sequence in self.cancelled_goal_sequences:
            self.cancelled_goal_sequences.discard(goal_sequence)
            try:
                handle = future.result()
                if handle.accepted:
                    handle.cancel_goal_async()
            except Exception as exc:
                self.get_logger().warn("已停止目标的延迟响应读取失败: %s", exc)
            return
        if goal_sequence != self.active_goal_sequence:
            return
        try:
            handle = future.result()
        except Exception as exc:
            self.goal_in_progress = False
            self._handle_navigation_failure(f"导航目标发送失败: {exc}")
            return

        if not handle.accepted:
            self.goal_in_progress = False
            self._handle_navigation_failure("导航目标被 Nav2 拒绝")
            return

        # A stop message may arrive while the action server is processing the
        # goal request, before goal_handle has been stored locally.
        if self.state == "TRAFFIC_STOPPED":
            self.goal_in_progress = False
            self.goal_handle = None
            self.active_goal_sequence = None
            handle.cancel_goal_async()
            return

        self.goal_handle = handle
        result_future = handle.get_result_async()
        result_future.add_done_callback(
            lambda result_future: self._goal_result_callback(
                result_future, goal_sequence
            )
        )

    def _goal_result_callback(self, future, goal_sequence) -> None:
        if goal_sequence != self.active_goal_sequence:
            return
        # A cancelled goal can still produce a result callback after a red
        # light event.  The stop state owns the next transition in that case.
        if self.state == "TRAFFIC_STOPPED":
            return

        self.goal_in_progress = False
        self.goal_handle = None
        self.active_goal_sequence = None
        self.navigation_deadline = None
        try:
            result = future.result()
            succeeded = result.status == GoalStatus.STATUS_SUCCEEDED
        except Exception as exc:
            self._handle_navigation_failure(f"导航结果读取失败: {exc}")
            return

        if not succeeded:
            self._handle_navigation_failure("Nav2 未成功到达目标")
            return

        self.navigation_retries = 0
        reached = self.current_goal_idx
        self.get_logger().info("已到达航点 %d", reached + 1)

        if reached == 3:
            self.state = "WAITING_GRASP"
            self.task_deadline = time.monotonic() + self.grasp_timeout_sec
            self.grasp_start_pub.publish(Bool(data=True))
            self.get_logger().info("已发布 /grasp/start=True，等待抓取完成")
        elif reached == 4:
            self.state = "WAITING_PLACE"
            self.task_deadline = time.monotonic() + self.place_timeout_sec
            self.place_start_pub.publish(Bool(data=True))
            self.get_logger().info("已发布 /place/start=True，等待放置完成")
        elif reached == len(self.waypoints) - 1:
            self._complete_mission()
        else:
            self.current_goal_idx += 1
            self._send_current_goal()

    def _watchdog_callback(self) -> None:
        now = time.monotonic()

        if self.state == "NAVIGATING" and self.navigation_deadline is not None:
            if now > self.navigation_deadline:
                self.navigation_deadline = None
                if self.goal_handle is not None:
                    self.goal_handle.cancel_goal_async()
                self.goal_handle = None
                self.goal_in_progress = False
                self.active_goal_sequence = None
                self._handle_navigation_failure(
                    f"导航目标超过 {self.navigation_timeout_sec:.0f}s 未完成"
                )
            return

        if self.state not in {"WAITING_GRASP", "WAITING_PLACE"}:
            self.task_deadline = None
            return
        if self.task_deadline is None or now <= self.task_deadline:
            return

        task_name = "抓取" if self.state == "WAITING_GRASP" else "放置"
        self.task_deadline = None
        self.get_logger().error(f"{task_name}等待超时，任务停止")
        self._fail_mission()

    def _handle_navigation_failure(self, reason: str) -> None:
        if self.state == "TRAFFIC_STOPPED":
            return

        self.get_logger().error(reason)
        self._publish_mission_status("NAVIGATION_FAILED", reason)
        self.goal_handle = None
        self.goal_in_progress = False
        self.navigation_deadline = None
        if self.navigation_retries < self.navigation_retry_limit:
            self.navigation_retries += 1
            self.get_logger().warn(
                "保留当前航点重试 (%d/%d)",
                self.navigation_retries,
                self.navigation_retry_limit,
            )
            self._send_current_goal()
            return

        self.get_logger().error("当前航点重试次数耗尽，任务停止")
        self._fail_mission()

    def _traffic_callback(self, message: Bool) -> None:
        if message.data:
            if self.state not in {"NAVIGATING", "IDLE"}:
                return
            if self.state == "TRAFFIC_STOPPED":
                return
            self.state_before_stop = self.state
            self.state = "TRAFFIC_STOPPED"
            goal_sequence = self.active_goal_sequence
            if self.goal_handle is not None and self.goal_in_progress:
                self.goal_handle.cancel_goal_async()
                self.goal_handle = None
                self.goal_in_progress = False
            elif self.goal_in_progress and goal_sequence is not None:
                self.cancelled_goal_sequences.add(goal_sequence)
                self.goal_in_progress = False
            self.active_goal_sequence = None
            self.navigation_deadline = None
            self._publish_mission_status("TRAFFIC_STOPPED", "红灯或 STOP")
            self.get_logger().warn("检测到红灯/STOP，暂停当前导航")
            return

        if self.state == "TRAFFIC_STOPPED":
            self.state = "IDLE"
            self.state_before_stop = None
            self._publish_mission_status("RESUMING", "交通信号恢复")
            self.get_logger().info("交通灯恢复，继续当前航点")
            self._send_current_goal()

    def _grasp_callback(self, message: Bool) -> None:
        if self.state != "WAITING_GRASP":
            return
        if message.data:
            self.task_deadline = None
            self._publish_mission_status("GRASP_SUCCEEDED", "抓取完成")
            self.current_goal_idx += 1
            self.state = "IDLE"
            self._send_current_goal()
        else:
            self.task_deadline = None
            self._publish_mission_status("GRASP_FAILED", "抓取节点报告失败")
            self._fail_mission()

    def _place_callback(self, message: Bool) -> None:
        if self.state != "WAITING_PLACE":
            return
        if message.data:
            self.task_deadline = None
            self._publish_mission_status("PLACE_SUCCEEDED", "放置完成")
            self.current_goal_idx += 1
            self.state = "IDLE"
            self._send_current_goal()
        else:
            self.task_deadline = None
            self._publish_mission_status("PLACE_FAILED", "放置节点报告失败")
            self._fail_mission()

    def _complete_mission(self) -> None:
        self.state = "DONE"
        self.navigation_deadline = None
        self.task_deadline = None
        self._publish_mission_status("SUCCEEDED", "完整移动操作任务完成")
        self.mission_success_pub.publish(Bool(data=True))
        self.get_logger().info("完整移动操作任务完成")
        if rclpy.ok():
            rclpy.shutdown()

    def _fail_mission(self) -> None:
        self.state = "FAILED"
        self._publish_mission_status("FAILED", "任务失败")
        self.mission_success_pub.publish(Bool(data=False))
        if rclpy.ok():
            rclpy.shutdown()

    def _publish_mission_status(self, status: str, detail: str) -> None:
        """Publish a compact machine-readable status for demos and logs."""
        self.mission_status_pub.publish(String(data=f"{status}: {detail}"))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FullMissionNavigator()
    try:
        node.start()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

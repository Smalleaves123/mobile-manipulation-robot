#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
import math
import time
import subprocess
import os
import signal
from dataclasses import dataclass

from geometry_msgs.msg import Pose, PoseArray, PoseStamped
from interbotix_xs_msgs.msg import JointGroupCommand, JointSingleCommand
from sensor_msgs.msg import JointState
from tf2_ros import TransformListener, Buffer
from tf2_geometry_msgs import do_transform_pose
from std_msgs.msg import Bool, String



@dataclass(frozen=True)
class GraspConfig:
    """Safety limits and vertical offsets for a PX100 top-down grasp."""

    hover_offset_z: float = 0.02
    grasp_offset_z: float = -0.02
    min_reach: float = 0.10
    max_reach: float = 0.32
    min_z: float = 0.005
    max_z: float = 0.30


@dataclass(frozen=True)
class GraspPlan:
    target: tuple[float, float, float]
    hover: tuple[float, float, float]
    grasp: tuple[float, float, float]


def build_grasp_plan(
    target: tuple[float, float, float], config: GraspConfig
) -> GraspPlan:
    """Validate a target in the PX100 base frame and create two poses."""
    if len(target) != 3:
        raise ValueError("抓取目标必须包含 x、y、z 三个坐标")

    x, y, z = (float(value) for value in target)
    reach = math.hypot(x, y)
    if not config.min_reach <= reach <= config.max_reach:
        raise ValueError(
            f"水平距离 {reach:.3f} m 超出 [{config.min_reach:.3f}, "
            f"{config.max_reach:.3f}] m"
        )
    if not config.min_z <= z <= config.max_z:
        raise ValueError(
            f"目标高度 {z:.3f} m 超出 [{config.min_z:.3f}, "
            f"{config.max_z:.3f}] m"
        )

    hover_z = min(config.max_z, z + config.hover_offset_z)
    grasp_z = max(config.min_z, z + config.grasp_offset_z)
    return GraspPlan(
        target=(x, y, z),
        hover=(x, y, hover_z),
        grasp=(x, y, grasp_z),
    )

class PX100Kinematics:
    def __init__(self):
        # 使用 robotics-toolbox 的 px100 内置模型
        import roboticstoolbox as rtb
        from spatialmath import SE3
        self._rtb = rtb
        self._SE3 = SE3
        self._robot = rtb.models.px100()
        self._ee_index = 11
        self._last_q = None

    def solve_ik(self, x, y, z, keep_level=True):
        pitch = 0.0 if keep_level else 0.0
        T = self._SE3(x, y, z) * self._SE3.Ry(pitch)
        mask = [1, 1, 1, 0, 1, 0]
        
        yaw0 = math.atan2(y, x)
        dist = math.sqrt(x**2 + y**2)
        
        initial_guesses = []
        
        if self._last_q is not None:
            initial_guesses.append(list(self._last_q))
        
        if z < 0.05:  # 物体很低
            initial_guesses.append([yaw0, -0.2, 1.4, -1.2])
        elif z < 0.1:  # 物体中等高度
            initial_guesses.append([yaw0, -0.4, 1.2, -0.8])
        else:  # 物体较高
            initial_guesses.append([yaw0, -0.5, 1.0, -0.5])
        
        initial_guesses.append([yaw0, -0.5, 1.0, -0.5])
        
        initial_guesses.append([yaw0, 0.0, 1.5, -1.5])
        
        for i, q0 in enumerate(initial_guesses):
            sol = self._robot.ikine_LM(
                T, 
                q0=q0, 
                end=self._robot[self._ee_index], 
                mask=mask,
                ilimit=500,      # 增加迭代次数限制（默认约100）
                slimit=200,      # 增加搜索步数限制
                tol=1e-5         # 稍微放宽收敛容差（默认1e-6）
            )
            if sol.success:
                self._last_q = sol.q
                if i > 0: 
                    print(f"✓ IK求解成功（尝试#{i+1}）")
                return list(sol.q)
        
        return None


class ArucoGraspNode(Node):
    def __init__(self):
        super().__init__("aruco_grasp_node")

        self.declare_parameter("vision_mode", "aruco")
        self.declare_parameter("allow_fixed_fallback", False)
        self.declare_parameter("fixed_target_x", 0.20)
        self.declare_parameter("fixed_target_y", 0.0)
        self.declare_parameter("fixed_target_z", 0.05)
        self.declare_parameter("search_timeout_sec", 15.0)
        self.declare_parameter("target_stability_tolerance", 0.02)
        self.declare_parameter("target_stability_frames", 6)
        self.declare_parameter("pan_tilt_pitch_deg", 37.0)
        self.declare_parameter("pan_tilt_settle_sec", 5.0)
        self.declare_parameter("detector_startup_sec", 2.0)
        self.declare_parameter("max_ik_retries", 2)
        self.declare_parameter("grasp_verification", "commanded")
        # iqr_tb4_bringup remaps /px100/joint_states to /joint_states.
        # Keep this configurable for older robot images.
        self.declare_parameter("gripper_state_topic", "/joint_states")
        self.declare_parameter("gripper_object_gap", 0.05)
        self.declare_parameter("grasp_verification_timeout_sec", 3.0)
        self.declare_parameter("gripper_open_position", 1.57)
        self.declare_parameter("gripper_close_position", 0.62)
        self.vision_mode = self.get_parameter("vision_mode").value
        self.vision_mode = str(self.vision_mode).lower()
        if self.vision_mode not in {"aruco", "box", "sam", "visual", "auto"}:
            self.get_logger().warn(
                "未知 vision_mode=%s，回退到 aruco", self.vision_mode
            )
            self.vision_mode = "aruco"
        self.allow_fixed_fallback = self.get_parameter("allow_fixed_fallback").value
        self.fixed_target = (
            float(self.get_parameter("fixed_target_x").value),
            float(self.get_parameter("fixed_target_y").value),
            float(self.get_parameter("fixed_target_z").value),
        )
        self.control_period_sec = 0.5
        self.max_search_ticks = max(
            1,
            math.ceil(
                float(self.get_parameter("search_timeout_sec").value)
                / self.control_period_sec
            ),
        )
        self.target_stability_tolerance = float(
            self.get_parameter("target_stability_tolerance").value
        )
        self.target_stability_frames = max(
            2, int(self.get_parameter("target_stability_frames").value)
        )
        self.pan_tilt_pitch_deg = float(
            self.get_parameter("pan_tilt_pitch_deg").value
        )
        self.pan_tilt_settle_ticks = max(
            1,
            math.ceil(
                float(self.get_parameter("pan_tilt_settle_sec").value)
                / self.control_period_sec
            ),
        )
        self.detector_startup_ticks = max(
            1,
            math.ceil(
                float(self.get_parameter("detector_startup_sec").value)
                / self.control_period_sec
            ),
        )
        self.max_ik_retries = max(
            0, int(self.get_parameter("max_ik_retries").value)
        )
        self.grasp_verification = str(
            self.get_parameter("grasp_verification").value
        ).lower()
        if self.grasp_verification not in {"commanded", "joint_state"}:
            self.get_logger().warn(
                "未知 grasp_verification=%s，回退到 commanded",
                self.grasp_verification,
            )
            self.grasp_verification = "commanded"
        self.gripper_object_gap = float(
            self.get_parameter("gripper_object_gap").value
        )
        self.gripper_open_position = float(
            self.get_parameter("gripper_open_position").value
        )
        self.gripper_close_position = float(
            self.get_parameter("gripper_close_position").value
        )
        self.grasp_verification_ticks = max(
            1,
            int(
                float(
                    self.get_parameter("grasp_verification_timeout_sec").value
                )
                * 2
            ),
        )
        
        self.pub_arm = self.create_publisher(JointGroupCommand, "/px100/commands/joint_group", 10)
        self.pub_gripper = self.create_publisher(JointSingleCommand, "/px100/commands/joint_single", 10)
        # 发布抓取成功话题
        self.pub_grasp_success = self.create_publisher(Bool, "/grasp/success", 10)
        self.pub_grasp_status = self.create_publisher(String, "/grasp/status", 10)

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.sub_poses = self.create_subscription(PoseArray, "/aruco_detector/marker_poses", self.cb_poses, 10)
        self.sub_joint_states = self.create_subscription(
            JointState,
            str(self.get_parameter("gripper_state_topic").value),
            self.cb_joint_states,
            10,
        )
        
        # 订阅启动话题
        self.sub_start = self.create_subscription(Bool, "/grasp/start", self.cb_start, 10)

        self.ik_solver = PX100Kinematics()
        
        # 等待启动信号
        self.started = False
        self.state = "WAITING_START"
        self.target_pose_base = None
        self.stable_counter = 0
        self.last_observed_position = None
        self.search_ticks = 0
        self.wait_ticks = 0
        self.verify_ticks = 0
        self.ik_failures = 0
        self.gripper_position = None
        self.grasp_verified = False
        self.failure_reason = ""
        self.detector_started = False
        self.visual_fallback_started = False
        self.timer = self.create_timer(self.control_period_sec, self.control_loop)
        
        # 高度配置
        self.HOVER_ADD_Z = 0.02
        self.GRASP_ADD_Z = -0.02
        self.grasp_config = GraspConfig(
            hover_offset_z=self.HOVER_ADD_Z,
            grasp_offset_z=self.GRASP_ADD_Z,
        )
        
        # ArUco检测进程
        self.aruco_process = None

        self.get_logger().info("✅ 节点启动: 等待 /grasp/start 话题中的 True 指令...")
        self._publish_status("WAITING_START", "等待 /grasp/start")

    def _publish_status(self, status: str, detail: str) -> None:
        """Publish a human-readable status without changing the Bool API."""
        self.pub_grasp_status.publish(String(data=f"{status}: {detail}"))

    def _reset_attempt(self) -> None:
        """Reset per-attempt state so a supervisor can retry safely."""
        self.target_pose_base = None
        self.stable_counter = 0
        self.last_observed_position = None
        self.search_ticks = 0
        self.wait_ticks = 0
        self.verify_ticks = 0
        self.ik_failures = 0
        self.gripper_position = None
        self.grasp_verified = False
        self.failure_reason = ""
        self.detector_started = False
        self.visual_fallback_started = False

    def _fail_grasp(self, reason: str) -> None:
        """Enter the common safe-failure path and report the reason."""
        self.failure_reason = reason
        self.get_logger().error("❌ 抓取失败: %s", reason)
        self._publish_status("FAILED", reason)
        self.state = "FAILED"

    def cb_start(self, msg: Bool):
        """接收启动信号"""
        if msg.data and (not self.started or self.state == "FINISHED"):
            self.get_logger().info("🚀 收到启动信号，开始执行抓取任务...")
            self._reset_attempt()
            self.started = True
            # 执行抓取前准备
            self.setup_before_grasp()
            # Do not sleep inside a ROS callback: a single-threaded executor
            # would stop receiving camera and joint-state messages.  The timer
            # performs the delayed detector startup below.
            self.state = "WAITING_VISION"
            self.wait_ticks = self.pan_tilt_settle_ticks
            self.search_ticks = 0
            self._publish_status("PREPARING", "云台调整中")

    def cb_poses(self, msg: PoseArray):
        if not self.started:
            return
        if self.state != "SEARCHING":
            return
        if len(msg.poses) == 0:
            self.stable_counter = 0
            self.last_observed_position = None
            return
        try:
            pose_base = self._select_target_pose(msg)
            if pose_base is None:
                self.stable_counter = 0
                self.last_observed_position = None
                return
            self.target_pose_base = pose_base
            current_position = (
                float(pose_base.position.x),
                float(pose_base.position.y),
                float(pose_base.position.z),
            )
            if self.last_observed_position is not None:
                delta = math.sqrt(
                    sum(
                        (current - previous) ** 2
                        for current, previous in zip(
                            current_position, self.last_observed_position
                        )
                    )
                )
            else:
                delta = float("inf")

            if delta <= self.target_stability_tolerance:
                self.stable_counter += 1
            else:
                self.stable_counter = 1
            self.last_observed_position = current_position

            if self.stable_counter >= self.target_stability_frames:
                self.state = "PREPARE_GRASP"
                self.stable_counter = 0
                self._publish_status("TARGET_STABLE", "视觉目标已稳定")
        except Exception as exc:
            self.get_logger().warn("解析视觉目标失败: %s", exc)

    def _select_target_pose(self, message: PoseArray):
        """Transform and select the most reachable candidate, not just pose 0."""
        candidates = []
        for pose in message.poses:
            target_cam = PoseStamped()
            target_cam.header = message.header
            target_cam.pose = pose
            try:
                transform = self.tf_buffer.lookup_transform(
                    "px100/base_link",
                    target_cam.header.frame_id,
                    rclpy.time.Time(),
                )
                pose_base = do_transform_pose(target_cam.pose, transform)
                build_grasp_plan(
                    (
                        pose_base.position.x,
                        pose_base.position.y,
                        pose_base.position.z,
                    ),
                    config=self.grasp_config,
                )
            except Exception:
                continue

            position = (
                float(pose_base.position.x),
                float(pose_base.position.y),
                float(pose_base.position.z),
            )
            if self.last_observed_position is None:
                score = math.hypot(position[0], position[1])
            else:
                score = math.sqrt(
                    sum(
                        (current - previous) ** 2
                        for current, previous in zip(
                            position, self.last_observed_position
                        )
                    )
                )
            candidates.append((score, pose_base))

        if not candidates:
            return None
        return min(candidates, key=lambda item: item[0])[1]

    def send_arm(self, joints):
        msg = JointGroupCommand()
        msg.name = "arm"
        msg.cmd = joints
        self.pub_arm.publish(msg)

    def send_gripper(self, val):
        msg = JointSingleCommand()
        msg.name = "gripper"
        msg.cmd = float(val)
        self.pub_gripper.publish(msg)

    def cb_joint_states(self, msg: JointState):
        """Cache the gripper joint position for optional grasp verification."""
        try:
            index = msg.name.index("gripper")
        except ValueError:
            return
        if index < len(msg.position):
            self.gripper_position = float(msg.position[index])

    def setup_before_grasp(self):
        """Start pan-tilt preparation without blocking ROS callbacks."""
        self.get_logger().info("🔧 抓取前准备：云台转动")
        
        # 1. 云台转动到30度
        try:
            cmd = (
                "ros2 topic pub --once /pan_tilt_cmd_deg "
                "pan_tilt_msgs/msg/PanTiltCmdDeg "
                f'"{{yaw: 0.0, pitch: {self.pan_tilt_pitch_deg}, speed: 10}}"'
            )
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.get_logger().info(
                "✅ 云台转动命令已发送: pitch=%.1f°", self.pan_tilt_pitch_deg
            )
        except Exception as e:
            self.get_logger().error(f"❌ 云台转动失败: {e}")
        
    def start_detector(self, force_visual=False):
        """Start the selected detector after the pan-tilt has settled."""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            detector_script = "aruco_detection_ros.py"
            if force_visual or self.vision_mode in {"box", "sam", "visual"}:
                detector_script = "visual_detection_ros.py"
            aruco_script = os.path.join(project_root, "detection", detector_script)
            
            self.aruco_process = subprocess.Popen(
                ["python3", aruco_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid  
            )
            self.detector_started = True
            self.get_logger().info(f"✅ {detector_script} 已启动 (PID: {self.aruco_process.pid})")
        except Exception as e:
            self.get_logger().error(f"❌ 目标检测启动失败: {e}")

    def _stop_detector_process(self):
        """Stop the child detector process without affecting other ROS nodes."""
        if self.aruco_process is None:
            return
        try:
            os.killpg(os.getpgid(self.aruco_process.pid), signal.SIGTERM)
            self.aruco_process.wait(timeout=3.0)
        except Exception as exc:
            self.get_logger().warn("目标检测进程关闭异常: %s", exc)
            try:
                os.killpg(os.getpgid(self.aruco_process.pid), signal.SIGKILL)
            except Exception:
                pass
        finally:
            self.aruco_process = None

    def cleanup_after_grasp(self, success=True, reason=""):
        """抓取后清理：云台恢复原位并关闭ArUco检测"""
        self.get_logger().info("🧹 抓取后清理：云台恢复 + ArUco检测关闭")
        
        # 1. 关闭ArUco检测进程
        if self.aruco_process is not None:
            self._stop_detector_process()
            self.get_logger().info("✅ 目标检测进程已关闭")
        
        # 2. 云台恢复到原位（pitch=0）
        try:
            cmd = 'ros2 topic pub --once /pan_tilt_cmd_deg pan_tilt_msgs/msg/PanTiltCmdDeg "{yaw: 0.0, pitch: 0.0, speed: 20}"'
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.get_logger().info("✅ 云台恢复命令已发送: pitch=0°")
        except Exception as e:
            self.get_logger().error(f"❌ 云台恢复失败: {e}")
        
        # 3. 发布抓取结果。默认模式沿用原项目行为；joint_state 模式
        # 只有通过启发式核验才会发布 True。
        success_msg = Bool(data=bool(success))
        self.pub_grasp_success.publish(success_msg)
        self._publish_status(
            "SUCCEEDED" if success else "FAILED",
            "完成" if success else (reason or "抓取未通过核验"),
        )
        self.get_logger().info(
            "抓取结果已发布: %s", "success" if success else "failed"
        )
        self.started = False
        self.detector_started = False

    def control_loop(self):
        if self.wait_ticks > 0:
            self.wait_ticks -= 1
            return

        if self.state == "WAITING_START":
            # 等待启动信号，不执行任何操作
            pass

        elif self.state == "WAITING_VISION":
            if not self.detector_started:
                self.start_detector()
            self.state = "SEARCHING"
            self.search_ticks = 0
            self.wait_ticks = self.detector_startup_ticks
            self._publish_status("SEARCHING", "等待视觉目标")

        elif self.state == "SEARCHING":
            self.search_ticks += 1
            if self.aruco_process is not None and self.aruco_process.poll() is not None:
                self.get_logger().error("目标检测进程已退出")
                self.aruco_process = None
            if (
                self.vision_mode == "auto"
                and not self.visual_fallback_started
                and self.search_ticks >= self.max_search_ticks
            ):
                self.get_logger().warn(
                    "ArUco 搜索超时，自动切换到无标记盒体视觉检测"
                )
                self._stop_detector_process()
                self.start_detector(force_visual=True)
                self.visual_fallback_started = True
                self.search_ticks = 0
                self.stable_counter = 0
                self.last_observed_position = None
                self.wait_ticks = self.detector_startup_ticks
                self._publish_status("BOX_FALLBACK", "ArUco 超时，切换无标记检测")
            elif self.allow_fixed_fallback and self.search_ticks >= self.max_search_ticks:
                self.get_logger().warn(
                    "⚠️ 未收到视觉目标，启用固定目标 fallback: "
                    f"{self.fixed_target}"
                )
                self.target_pose_base = Pose()
                self.target_pose_base.position.x = self.fixed_target[0]
                self.target_pose_base.position.y = self.fixed_target[1]
                self.target_pose_base.position.z = self.fixed_target[2]
                self.state = "PREPARE_GRASP"
                self.search_ticks = 0
                self._publish_status("FIXED_FALLBACK", "视觉超时，使用固定目标")
            elif not self.allow_fixed_fallback and self.search_ticks >= self.max_search_ticks:
                self._fail_grasp("视觉搜索超时，未检测到可达目标")

        elif self.state == "PREPARE_GRASP":
            self.get_logger().info("1. 准备：抬起手臂")
            self.send_gripper(self.gripper_open_position)
            self.send_arm([0.0, -0.3, 0.48, 0.0]) 
            self.state = "MOVE_HOVER" 
            self.wait_ticks = 4 
            self._publish_status("MOVE_HOVER", "移动到目标上方")

        elif self.state == "MOVE_HOVER":
            if not self.target_pose_base: 
                self.state = "SEARCHING"
                return

            x = self.target_pose_base.position.x
            y = self.target_pose_base.position.y
            z_aruco = self.target_pose_base.position.z

            try:
                plan = build_grasp_plan(
                    (x, y, z_aruco),
                    config=self.grasp_config,
                )
            except ValueError as exc:
                self.get_logger().error(f"❌ 目标不在安全抓取范围: {exc}")
                self.state = "SEARCHING"
                return

            z_target = plan.hover[2]
            
            # Debug: 打印距离
            dist = math.sqrt(x**2 + y**2)
            self.get_logger().info(f"2. 悬停 (Z={z_target:.3f}, Dist={dist:.3f})")
            
            joints = self.ik_solver.solve_ik(plan.hover[0], plan.hover[1], z_target)
            
            if joints:
                self.send_arm(joints)
                self.state = "MOVE_DOWN" 
                self.wait_ticks = 5     
            else:
                self.get_logger().error("❌ 悬停 IK 失败 (物体可能太近)")
                self.ik_failures += 1
                if self.ik_failures > self.max_ik_retries:
                    self._fail_grasp("悬停 IK 多次失败")
                else:
                    self.state = "SEARCHING"

        elif self.state == "MOVE_DOWN":
            x = self.target_pose_base.position.x
            y = self.target_pose_base.position.y
            z_aruco = self.target_pose_base.position.z

            try:
                plan = build_grasp_plan(
                    (x, y, z_aruco),
                    config=self.grasp_config,
                )
            except ValueError as exc:
                self.get_logger().error(f"❌ 目标不在安全抓取范围: {exc}")
                self.state = "SEARCHING"
                return

            z_target = plan.grasp[2]

            self.get_logger().info(f"3. 下落 (Z={z_target:.3f})")
            joints = self.ik_solver.solve_ik(plan.grasp[0], plan.grasp[1], z_target)

            if joints:
                self.send_arm(joints)
                self.state = "CLOSE"
                self.wait_ticks = 4
                self._publish_status("CLOSING", "移动到抓取高度")
            else:
                self.get_logger().error("❌ 下落 IK 失败 (物体太近或太低)")
                self.ik_failures += 1
                if self.ik_failures > self.max_ik_retries:
                    self._fail_grasp("下落 IK 多次失败")
                else:
                    self.state = "SEARCHING"

        elif self.state == "CLOSE":
            self.get_logger().info("4. 闭合")
            self.send_gripper(self.gripper_close_position)
            if self.grasp_verification == "joint_state":
                self.state = "VERIFY_GRASP"
                self.verify_ticks = 0
            else:
                # Compatibility mode: the original project had no tactile or
                # force feedback and treats the completed command as success.
                self.grasp_verified = True
                self.state = "RETRACT"
            self.wait_ticks = 3 

        elif self.state == "VERIFY_GRASP":
            self.verify_ticks += 1
            if self.gripper_position is not None:
                # The PX100 command convention used here is approximately
                # 1.57=open and 0.62=closed.  A position that remains above
                # the closed target suggests an object is holding the jaws.
                self.grasp_verified = (
                    self.gripper_position
                    > self.gripper_close_position + self.gripper_object_gap
                )
                if self.grasp_verified:
                    self.get_logger().info(
                        "夹爪位置显示仍有间隙，启发式判断为可能夹住物体"
                    )
                    self.state = "RETRACT"
                elif self.verify_ticks >= self.grasp_verification_ticks:
                    self.get_logger().error(
                        "夹爪已接近完全闭合，未通过可选抓取核验"
                    )
                    self._fail_grasp("夹爪闭合间隙不足，未通过抓取核验")
            elif self.verify_ticks >= self.grasp_verification_ticks:
                self.get_logger().error(
                    "未收到夹爪关节状态，无法完成 joint_state 抓取核验"
                )
                self._fail_grasp("未收到夹爪关节状态，无法完成抓取核验")

        elif self.state == "RETRACT":
            self.get_logger().info("5. 收回")
            self.send_arm([1.57, -0.3, 1.57, -1.3])
            self.state = "DONE"
            self.wait_ticks = 4

        elif self.state == "DONE":
            self.get_logger().info("✅ 抓取完成")
            # 执行抓取后清理
            self.cleanup_after_grasp(success=self.grasp_verified)
            self.state = "FINISHED"

        elif self.state == "FAILED":
            self.get_logger().error("❌ 抓取流程失败，不发布成功信号")
            # 核验失败时先把机械臂收回安全位，再清理视觉进程。
            self.send_arm([1.57, -0.3, 1.57, -1.3])
            self.cleanup_after_grasp(success=False, reason=self.failure_reason)
            self.state = "FINISHED"
            
        elif self.state == "FINISHED":
            # 保持在完成状态，不再执行任何操作
            pass

def main():
    rclpy.init()
    node = ArucoGraspNode()
    
    rclpy.spin(node)
    
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

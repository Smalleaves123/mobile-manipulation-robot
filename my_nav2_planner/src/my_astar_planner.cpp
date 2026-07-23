#include "my_nav2_planner/my_astar_planner.hpp"
#include "pluginlib/class_list_macros.hpp"
#include "nav2_util/node_utils.hpp"

#include <queue>
#include <cmath>
#include <algorithm>
#include <chrono>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

// 注册插件
PLUGINLIB_EXPORT_CLASS(my_nav2_planner::MyAStarPlanner, nav2_core::GlobalPlanner)

namespace my_nav2_planner
{

// A* 节点结构
struct Node {
    int x, y;
    double g_cost;
    double h_cost;
    double f_cost;
    int parent_index;

    // 优先队列需要重载 > 运算符 (小顶堆)
    bool operator>(const Node& other) const {
        return f_cost > other.f_cost;
    }
};

MyAStarPlanner::MyAStarPlanner() : costmap_(nullptr), initialized_(false) {}

MyAStarPlanner::~MyAStarPlanner() {}

void MyAStarPlanner::configure(
  const rclcpp_lifecycle::LifecycleNode::WeakPtr & parent,
  std::string name, std::shared_ptr<tf2_ros::Buffer> /*tf*/,
  std::shared_ptr<nav2_costmap_2d::Costmap2DROS> costmap_ros)
{
  node_ = parent.lock();
  if (!node_) {
    throw std::runtime_error("MyAStarPlanner received an expired lifecycle node");
  }
  if (!costmap_ros) {
    throw std::runtime_error("MyAStarPlanner received a null costmap");
  }

  name_ = name;
  costmap_ros_ = costmap_ros;
  costmap_ = costmap_ros_->getCostmap(); // 获取原始地图指针
  global_frame_ = costmap_ros_->getGlobalFrameID();

  // Nav2 namespaces plugin parameters as <plugin_name>.<parameter>.
  auto declare_if_needed = [this](const std::string & parameter_name, auto default_value) {
    if (!node_->has_parameter(parameter_name)) {
      node_->declare_parameter(parameter_name, default_value);
    }
  };
  declare_if_needed(name_ + ".use_8_neighbors", false);
  declare_if_needed(name_ + ".allow_unknown", false);
  declare_if_needed(name_ + ".cost_weight", 0.0);
  declare_if_needed(name_ + ".timeout_ms", 5000.0);
  node_->get_parameter(name_ + ".use_8_neighbors", use_8_neighbors_);
  node_->get_parameter(name_ + ".allow_unknown", allow_unknown_);
  node_->get_parameter(name_ + ".cost_weight", cost_weight_);
  node_->get_parameter(name_ + ".timeout_ms", timeout_ms_);
  cost_weight_ = std::clamp(cost_weight_, 0.0, 1.0);
  timeout_ms_ = std::max(1.0, timeout_ms_);
  
  RCLCPP_INFO(
    node_->get_logger(),
    "配置 MyAStarPlanner: %s (neighbors=%s, allow_unknown=%s, "
    "cost_weight=%.2f, timeout_ms=%.1f)",
    name_.c_str(), use_8_neighbors_ ? "8" : "4",
    allow_unknown_ ? "true" : "false", cost_weight_, timeout_ms_);
  initialized_ = true;
}

void MyAStarPlanner::cleanup()
{
  RCLCPP_INFO(node_->get_logger(), "清理 MyAStarPlanner: %s", name_.c_str());
  costmap_ros_ = nullptr;
  costmap_ = nullptr;
  initialized_ = false;
}

void MyAStarPlanner::activate()
{
  RCLCPP_INFO(node_->get_logger(), "激活 MyAStarPlanner: %s", name_.c_str());
}

void MyAStarPlanner::deactivate()
{
  RCLCPP_INFO(node_->get_logger(), "停用 MyAStarPlanner: %s", name_.c_str());
}


nav_msgs::msg::Path MyAStarPlanner::createPlan(
  const geometry_msgs::msg::PoseStamped & start,
  const geometry_msgs::msg::PoseStamped & goal)
{
  nav_msgs::msg::Path global_path;
  global_path.header.stamp = node_->now();
  global_path.header.frame_id = global_frame_;

  if (!initialized_) {
    RCLCPP_ERROR(node_->get_logger(), "规划器未初始化");
    return global_path;
  }
  if (!costmap_) {
    RCLCPP_ERROR(node_->get_logger(), "代价地图不可用");
    return global_path;
  }

  // Nav2 passes poses in the planner's global frame.  Refuse a mismatched
  // frame instead of silently interpreting its coordinates as map coordinates.
  if ((!start.header.frame_id.empty() && start.header.frame_id != global_frame_) ||
    (!goal.header.frame_id.empty() && goal.header.frame_id != global_frame_))
  {
    RCLCPP_ERROR(
      node_->get_logger(),
      "规划请求坐标系不匹配: start='%s', goal='%s', expected='%s'",
      start.header.frame_id.c_str(), goal.header.frame_id.c_str(), global_frame_.c_str());
    return global_path;
  }

  // 坐标转换 World -> Map
  unsigned int mx_start, my_start, mx_goal, my_goal;
  if (!costmap_->worldToMap(start.pose.position.x, start.pose.position.y, mx_start, my_start)) {
    RCLCPP_ERROR(node_->get_logger(), "起点在地图外");
    return global_path;
  }
  if (!costmap_->worldToMap(goal.pose.position.x, goal.pose.position.y, mx_goal, my_goal)) {
    RCLCPP_ERROR(node_->get_logger(), "终点在地图外");
    return global_path;
  }
  if (!isSafe(mx_start, my_start) || !isSafe(mx_goal, my_goal)) {
    RCLCPP_ERROR(node_->get_logger(), "起点或终点位于障碍物/未知区域");
    return global_path;
  }

  // 初始化数据结构
  const unsigned int size_x = costmap_->getSizeInCellsX();
  const unsigned int size_y = costmap_->getSizeInCellsY();
  const std::size_t map_size = static_cast<std::size_t>(size_x) * size_y;
  if (map_size == 0 || map_size > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
    RCLCPP_ERROR(node_->get_logger(), "代价地图尺寸无效或过大");
    return global_path;
  }

  // OpenList (优先队列)
  std::priority_queue<Node, std::vector<Node>, std::greater<Node>> open_list;
  
  // Visited 表 (记录是否访问过)
  std::vector<bool> visited(map_size, false);
  
  // Parent 表 (记录父节点索引，用于回溯，-1表示无父节点)
  std::vector<int> parent_indices(map_size, -1);

  // G Cost 表 (记录到某点的最小代价，初始化为无穷大)
  std::vector<double> g_costs(map_size, std::numeric_limits<double>::infinity());

  // 起点入队
  int start_index = costmap_->getIndex(mx_start, my_start);
  g_costs[start_index] = 0.0;
  
  Node start_node;
  start_node.x = mx_start;
  start_node.y = my_start;
  start_node.g_cost = 0.0;
  start_node.h_cost = getHeuristic(mx_start, my_start, mx_goal, my_goal);
  start_node.f_cost = start_node.g_cost + start_node.h_cost;
  start_node.parent_index = -1;

  open_list.push(start_node);

  // A* 主循环。默认保留原来的 4 邻域，参数开启时支持对角线。
  std::vector<std::pair<int, int>> directions = {
    {0, 1}, {0, -1}, {1, 0}, {-1, 0}};
  if (use_8_neighbors_) {
    directions.insert(directions.end(), {
      {1, 1}, {1, -1}, {-1, 1}, {-1, -1}});
  }
  
  bool found_path = false;
  int goal_index = costmap_->getIndex(mx_goal, my_goal);
  const auto search_started = std::chrono::steady_clock::now();

  while (!open_list.empty()) {
    const auto elapsed_ms = std::chrono::duration<double, std::milli>(
      std::chrono::steady_clock::now() - search_started).count();
    if (elapsed_ms > timeout_ms_) {
      RCLCPP_WARN(node_->get_logger(), "A* 规划超时 (%.1f ms)", elapsed_ms);
      break;
    }

    Node current = open_list.top();
    open_list.pop();

    int current_index = costmap_->getIndex(current.x, current.y);

    // 如果已经处理过该节点则跳过
    if (visited[current_index]) continue;
    if (current.g_cost > g_costs[current_index] + 1e-9) continue;
    visited[current_index] = true;

    // 到达终点
    if (current_index == goal_index) {
      found_path = true;
      break;
    }

    // 扩展邻居
    for (const auto & direction : directions) {
      int nx = current.x + direction.first;
      int ny = current.y + direction.second;

      // 边界检查
      if (nx < 0 || nx >= static_cast<int>(size_x) ||
        ny < 0 || ny >= static_cast<int>(size_y)) continue;

      // 碰撞检测
      if (!isSafe(nx, ny)) continue;

      // 禁止对角线从两个障碍物的夹角中穿过，避免机器人 footprint
      // 实际碰撞而栅格路径仍然看起来可行。
      if (direction.first != 0 && direction.second != 0) {
        if (!isSafe(current.x + direction.first, current.y) ||
          !isSafe(current.x, current.y + direction.second)) {
          continue;
        }
      }

      int neighbor_index = costmap_->getIndex(nx, ny);
      const double step_cost = std::hypot(
        static_cast<double>(direction.first), static_cast<double>(direction.second));
      const double cell_cost = static_cast<double>(costmap_->getCost(nx, ny)) / 254.0;
      double new_g_cost = current.g_cost + step_cost + cost_weight_ * cell_cost;

      // 如果发现更优路径
      if (new_g_cost < g_costs[neighbor_index]) {
        g_costs[neighbor_index] = new_g_cost;
        parent_indices[neighbor_index] = current_index;

        Node neighbor;
        neighbor.x = nx;
        neighbor.y = ny;
        neighbor.g_cost = new_g_cost;
        neighbor.h_cost = getHeuristic(nx, ny, mx_goal, my_goal);
        neighbor.f_cost = new_g_cost + neighbor.h_cost;
        
        open_list.push(neighbor);
      }
    }
  }

  // 路径回溯
  if (found_path) {
    std::vector<geometry_msgs::msg::PoseStamped> path_poses;
    int curr = goal_index;

    while (curr != -1) {
      unsigned int mx, my;
      costmap_->indexToCells(curr, mx, my);
      
      double wx, wy;
      costmap_->mapToWorld(mx, my, wx, wy);

      geometry_msgs::msg::PoseStamped pose;
      pose.header = global_path.header;
      pose.pose.position.x = wx;
      pose.pose.position.y = wy;
      pose.pose.position.z = 0.0;

      path_poses.push_back(pose);
      curr = parent_indices[curr];
    }
    
    // 反转路径 (从起点到终点)
    std::reverse(path_poses.begin(), path_poses.end());
    for (std::size_t i = 0; i < path_poses.size(); ++i) {
      const std::size_t next = (i + 1 < path_poses.size()) ? i + 1 : i;
      const std::size_t previous = (i > 0) ? i - 1 : i;
      const double dx = path_poses[next].pose.position.x -
        path_poses[previous].pose.position.x;
      const double dy = path_poses[next].pose.position.y -
        path_poses[previous].pose.position.y;
      const double yaw = std::atan2(dy, dx);
      path_poses[i].pose.orientation.z = std::sin(yaw / 2.0);
      path_poses[i].pose.orientation.w = std::cos(yaw / 2.0);
    }
    global_path.poses = path_poses;
    
    RCLCPP_INFO(node_->get_logger(), "成功规划路径，长度: %zu", global_path.poses.size());
  } else {
    RCLCPP_WARN(node_->get_logger(), "A* 无法找到路径");
  }

  return global_path;
}

// 启发式函数: 欧几里得距离
double MyAStarPlanner::getHeuristic(int x1, int y1, int x2, int y2) {
  return std::hypot(x2 - x1, y2 - y1);
}

// 碰撞检测
bool MyAStarPlanner::isSafe(unsigned int x, unsigned int y) {
  unsigned char cost = costmap_->getCost(x, y);
  // LETHAL_OBSTACLE = 254, INSCRIBED = 253, NO_INFORMATION = 255
  if (cost == nav2_costmap_2d::NO_INFORMATION) {
    return allow_unknown_;
  }
  if (cost >= nav2_costmap_2d::INSCRIBED_INFLATED_OBSTACLE)
  {
    return false;
  }
  return true;
}

}  // namespace my_nav2_planner

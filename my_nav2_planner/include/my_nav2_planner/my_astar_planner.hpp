#ifndef MY_NAV2_PLANNER__MY_ASTAR_PLANNER_HPP_
#define MY_NAV2_PLANNER__MY_ASTAR_PLANNER_HPP_

#include <memory>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"
#include "nav2_core/global_planner.hpp"
#include "nav_msgs/msg/path.hpp"
#include "nav2_costmap_2d/costmap_2d_ros.hpp"
#include "nav2_costmap_2d/cost_values.hpp"
#include "tf2_ros/buffer.h"

namespace my_nav2_planner
{

class MyAStarPlanner : public nav2_core::GlobalPlanner
{
public:
  MyAStarPlanner();
  ~MyAStarPlanner();

  // 插件生命周期管理接口
  void configure(
    const rclcpp_lifecycle::LifecycleNode::WeakPtr & parent,
    std::string name, std::shared_ptr<tf2_ros::Buffer> tf,
    std::shared_ptr<nav2_costmap_2d::Costmap2DROS> costmap_ros) override;

  void cleanup() override;
  void activate() override;
  void deactivate() override;

  // 核心规划接口
  nav_msgs::msg::Path createPlan(
    const geometry_msgs::msg::PoseStamped & start,
    const geometry_msgs::msg::PoseStamped & goal) override;

private:
  // 坐标转换与辅助函数
  double getHeuristic(int x1, int y1, int x2, int y2);
  bool isSafe(unsigned int x, unsigned int y);

  // 成员变量
  // GlobalPlanner::configure receives an rclcpp_lifecycle node.  Store the
  // exact base type so parent.lock() is type-correct on Nav2 Humble.
  rclcpp_lifecycle::LifecycleNode::SharedPtr node_;
  std::shared_ptr<nav2_costmap_2d::Costmap2DROS> costmap_ros_;
  nav2_costmap_2d::Costmap2D * costmap_;
  std::string global_frame_;
  std::string name_;
  bool initialized_;
  bool use_8_neighbors_{false};
  bool allow_unknown_{false};
  double cost_weight_{0.0};
  double timeout_ms_{5000.0};
};

}  // namespace my_nav2_planner

#endif  // MY_NAV2_PLANNER__MY_ASTAR_PLANNER_HPP_

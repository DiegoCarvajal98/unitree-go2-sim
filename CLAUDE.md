# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Run

```bash
# One-time host prerequisite: install nvidia-container-toolkit, then restart Docker
# (see Phase 0 in the original plan)

# Build all Docker images (base → overlay → dev)
./scripts/build.sh

# Launch the simulation (Gazebo Fortress + CHAMP + ROS 2)
./scripts/run_sim.sh

# Attach a shell to the running sim container
docker compose exec sim bash

# Dev shell with live-editable source mounts
docker compose run --rm dev bash
```

When editing `src/go2_ign_bringup/` in the dev container, run colcon inside the container to rebuild:

```bash
cd /overlay_ws && colcon build --symlink-install --packages-select go2_ign_bringup
source install/setup.bash
```

Send velocity commands to make the robot walk:

```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.3}, angular: {z: 0.0}}"
```

## Architecture

The project is a 3-layer Docker build that wires together upstream packages with a thin custom bringup layer.

**Docker stages** (`docker/Dockerfile`):
- `base` — apt-installs ROS 2 Humble, Gazebo Fortress integration, ros2_control; clones `anujjain-dev/unitree-go2-ros2` (which bundles CHAMP + go2_description + go2_config); applies sed patches to swap Classic Gazebo plugins for Fortress ones; builds the full upstream workspace at `/go2_ws`
- `overlay` — copies `src/go2_ign_bringup/` and builds it at `/overlay_ws` with both workspaces sourced
- `dev` — adds user `diego` (UID 1000) and volume-mounts `src/go2_ign_bringup/` for live editing

**Custom package** (`src/go2_ign_bringup/`):
- `launch/go2_sim.launch.py` — orchestrates everything: robot_state_publisher → Gazebo Fortress → spawn robot → ros_ign_bridge → controllers (5s delayed) → CHAMP bringup → optional RViz2
- `config/go2_controllers.yaml` — defines `joint_states_controller` (JointStateBroadcaster) and `joint_group_effort_controller` (JointTrajectoryController with effort interface)
- `config/gz_bridge.yaml` — bridges `/clock`, `/tf`, `/imu/data` between Gazebo and ROS
- `worlds/go2_world.sdf` — Fortress world with ground plane and standard plugins

**Upstream source** (`src/unitree-go2-ros2/`):
- `robots/descriptions/go2_description/xacro/` — URDF xacros; `robot.xacro` is the entry point; `gazebo.xacro` and `leg.xacro` are patched in-Dockerfile
- `robots/configs/go2_config/config/` — joints/links/gait YAML consumed by CHAMP bringup
- `champ/champ_bringup/launch/bringup.launch.py` — the CHAMP locomotion controller; receives `/cmd_vel`, outputs joint trajectories

## Critical: Gazebo Fortress vs Classic Plugin Names

ROS 2 Humble uses **Gazebo Fortress (Ignition 6)**. All plugin names differ from Gazebo Classic:

| What | Classic (wrong) | Fortress (correct) |
|---|---|---|
| ros2_control filename | `libgazebo_ros2_control.so` | `ign_ros2_control-system` |
| ros2_control plugin name | `gazebo_ros2_control` | `ign_ros2_control::IgnitionROS2ControlPlugin` |
| Hardware interface | `gazebo_ros2_control/GazeboSystem` | `ign_ros2_control/IgnitionSystem` |
| SDF plugin namespace | `gz::sim::systems::` | `ignition::gazebo::systems::` |
| Apt package prefix | `ros-humble-ros-gz-*` | `ros-humble-ros-ign-*` |
| Python launch package | `ros_gz_gazebo` | `ros_ign_gazebo` |

The upstream URDF ships with Classic names; the Dockerfile sed-patches them at build time.

## Joint Names and Controller

All 12 joints use the `lf/rf/lh/rh` prefix (left-front / right-front / left-hind / right-hind):

```
lf_hip_joint  lf_upper_leg_joint  lf_lower_leg_joint
rf_hip_joint  rf_upper_leg_joint  rf_lower_leg_joint
lh_hip_joint  lh_upper_leg_joint  lh_lower_leg_joint
rh_hip_joint  rh_upper_leg_joint  rh_lower_leg_joint
```

The controller is `joint_trajectory_controller/JointTrajectoryController` with **effort** command interface (not position). CHAMP publishes to `/joint_group_effort_controller/joint_trajectory`.

## Workspace Layout Inside Containers

```
/opt/ros/humble/       — ROS 2 Humble install
/go2_ws/               — upstream workspace (CHAMP + go2_description + go2_config)
/overlay_ws/           — custom go2_ign_bringup package
/entrypoint.sh         — sources all three in order; sets IGN_GAZEBO_* env vars
```

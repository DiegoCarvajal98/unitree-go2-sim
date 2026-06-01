# Unitree Go2 Simulation — ROS 2 Humble + Gazebo Fortress

A fully containerized simulation of the [Unitree Go2](https://www.unitree.com/go2/) quadruped robot using ROS 2 Humble, Gazebo Fortress (Ignition 6), and the [CHAMP](https://github.com/chvmp/champ) locomotion controller. The robot walks in response to velocity commands, with GPU-accelerated rendering via NVIDIA Docker. A 2D LiDAR sensor enables SLAM-based mapping and Nav2 autonomous navigation in an industrial warehouse environment.

---

## Requirements

| Requirement | Notes |
|---|---|
| Ubuntu 22.04 | Host OS |
| NVIDIA GPU | Any CUDA-capable card |
| [NVIDIA driver](https://ubuntu.com/server/docs/nvidia-drivers-installation) | 525+ recommended |
| [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) | For GPU passthrough into Docker |
| Docker Engine + Compose v2 | `docker compose` (not `docker-compose`) |

### Install nvidia-container-toolkit (one-time host setup)

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Verify:
```bash
docker info | grep -i nvidia   # should list nvidia runtime
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/DiegoCarvajal98/unitree-go2-sim.git
cd unitree-go2-sim

# 2. Build Docker images (~15–30 min first time)
./scripts/build.sh

# 3. Launch the simulation
./scripts/run_sim.sh
```

Gazebo Fortress opens with the Go2 in the industrial warehouse world. The CHAMP locomotion controller and 2D LiDAR start automatically.

---

## Basic Control

Attach to the running container in a second terminal:

```bash
docker compose exec sim bash
```

Send velocity commands to make the robot walk:

```bash
# Walk forward
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.3}, angular: {z: 0.0}}"

# Turn left
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2}, angular: {z: 0.5}}"

# Stop
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{}"
```

Or use keyboard teleoperation:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

---

## 2D LiDAR

The robot carries a front-mounted 2D LiDAR (`front_laser` link, 0.225 m forward, 0.105 m up from `base_link`):

| Parameter | Value |
|---|---|
| Sensor type | `gpu_lidar` (Ignition Fortress native) |
| Field of view | 360° |
| Samples | 720 |
| Range | 0.12 – 25.0 m |
| Update rate | 10 Hz |
| ROS topic | `/scan` (`sensor_msgs/msg/LaserScan`) |

Verify the sensor is publishing:
```bash
ros2 topic hz /scan          # expect ~10 Hz
ros2 topic echo /scan --once
```

---

## Autonomous Navigation (go2_nav)

### Square trajectory

```bash
# 1 m sides, default speed
ros2 launch go2_nav square.launch.py

# 2 m sides, faster, looping
ros2 launch go2_nav square.launch.py side_length:=2.0 linear_speed:=0.3 loop:=true
```

| Parameter | Default | Description |
|---|---|---|
| `side_length` | `1.0` | Side length in metres |
| `linear_speed` | `0.25` | Forward speed (m/s) |
| `angular_speed` | `0.5` | Turn speed (rad/s) |
| `loop` | `false` | Repeat indefinitely |

### SLAM — build a map

With the simulation running, open a second shell in the dev container:

```bash
ros2 launch go2_nav slam.launch.py
```

Drive the robot around the warehouse with teleop to cover all areas, then save the map:

```bash
ros2 run nav2_map_server map_saver_cli -f ~/warehouse_map
```

### Nav2 — autonomous navigation on a saved map

```bash
ros2 launch go2_nav nav2.launch.py \
  map_yaml:=/root/warehouse_map.yaml \
  use_rviz:=true
```

Send navigation goals via the **Nav2 Goal** tool in RViz2, or with the action client:

```bash
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: map}, pose: {position: {x: 3.0, y: 1.0}}}}"
```

---

## Repository Structure

```
unitree-go2-sim/
├── docker/
│   ├── Dockerfile          # 3-stage build: base → overlay → dev
│   └── entrypoint.sh       # Sources all ROS workspaces; sets IGN_GAZEBO_* env vars
├── docker-compose.yml      # Services: base, overlay, sim, dev
├── .env                    # DISPLAY and USER_UID for compose
├── scripts/
│   ├── build.sh            # docker compose build (all stages)
│   └── run_sim.sh          # xhost + docker compose run --rm sim
└── src/
    ├── go2_ign_bringup/    # Gazebo Fortress bringup package
    │   ├── launch/
    │   │   └── go2_sim.launch.py       # Main launch file
    │   ├── xacro/
    │   │   ├── go2_with_lidar.xacro   # Wrapper: robot + LiDAR
    │   │   └── lidar_ign.xacro        # Fortress gpu_lidar sensor definition
    │   ├── config/
    │   │   ├── go2_controllers.yaml   # ros2_control: effort JointTrajectoryController
    │   │   └── gz_bridge.yaml         # ROS↔Gazebo topic bridge
    │   └── worlds/
    │       ├── industrial.sdf         # Industrial warehouse (default)
    │       └── go2_world.sdf          # Simple flat world
    └── go2_nav/            # Navigation nodes
        ├── go2_nav/
        │   ├── square_trajectory.py  # Timed square trajectory node
        │   ├── scan_frame_relay.py   # Republishes /scan_raw → /scan with correct frame_id
        │   └── imu_frame_relay.py    # Republishes /imu_raw → /imu/data with frame_id=imu_link
        ├── config/
        │   ├── nav2_params.yaml      # Nav2 stack parameters
        │   └── slam_params.yaml      # SLAM Toolbox parameters
        ├── maps/
        │   ├── industrial_map.pgm    # Saved occupancy grid (industrial warehouse)
        │   └── industrial_map.yaml   # Map metadata (resolution, origin, thresholds)
        └── launch/
            ├── square.launch.py      # Square trajectory
            ├── slam.launch.py        # SLAM mapping
            └── nav2.launch.py        # Nav2 with AMCL on saved map
```

> `src/unitree-go2-ros2/` is not tracked in git — it is cloned automatically during the Docker build from [anujjain-dev/unitree-go2-ros2](https://github.com/anujjain-dev/unitree-go2-ros2), which bundles CHAMP, `go2_description`, and `go2_config`.

---

## Architecture

### Docker Stages

**`base`** — Installs ROS 2 Humble, Gazebo Fortress integration packages (`ros-humble-ros-ign-*`, `ros-humble-ign-ros2-control`, `ros-humble-navigation2`, `ros-humble-slam-toolbox`), clones the upstream `unitree-go2-ros2` monorepo, applies URDF patches, and builds everything at `/go2_ws`.

**`overlay`** — Copies `src/go2_ign_bringup/` and `src/go2_nav/` into `/overlay_ws` and builds them with both the ROS install and `/go2_ws` sourced.

**`dev`** — Adds a non-root user (`diego`, UID 1000) with both packages volume-mounted for live editing.

### Workspace Layout Inside Containers

```
/opt/ros/humble/    — ROS 2 Humble install
/go2_ws/            — upstream CHAMP + go2_description + go2_config
/overlay_ws/        — go2_ign_bringup + go2_nav
/entrypoint.sh      — sources all three; sets IGN_GAZEBO_* paths
```

### Launch Sequence (`go2_sim.launch.py`)

1. `robot_state_publisher` — publishes the Go2 URDF (with LiDAR) to `/robot_description`
2. Gazebo Fortress — loads `industrial.sdf` (override with `world_file:=...`)
3. `ros_ign_gazebo create` — spawns the robot at z=0.35 m
4. `ros_ign_bridge` — bridges `/clock`, `/tf`, `/imu_raw`, `/scan`
5. *(5 s delay)* `joint_states_controller` spawner
6. `joint_group_effort_controller` spawner (after joint_states_controller exits)
7. `champ_bringup` — CHAMP locomotion; subscribes `/cmd_vel`, publishes joint trajectories
8. `imu_frame_relay` — republishes `/imu_raw` as `/imu/data` with `frame_id=imu_link`
9. `scan_frame_relay` — republishes `/scan_raw` as `/scan` with `frame_id=front_laser`
10. *(15 s delay)* RViz2 (optional, `use_rviz:=true`)

### LiDAR Integration Notes

Fortress scopes sensor frame IDs as `{model}/{link}/{sensor_name}`. A zero static transform is published from `front_laser` (URDF frame) to `go2/base_link/front_laser_sensor` (Ignition frame) so SLAM and Nav2 can resolve the sensor pose through the TF tree.

The `scan_frame_relay` node (`go2_nav`) subscribes to `/scan_raw` (the raw bridge topic, which carries the Ignition-scoped frame_id `go2/base_link/front_laser_sensor`) and republishes to `/scan` with `frame_id=front_laser`, keeping SLAM Toolbox's TF lookups consistent.

The URDF entry point is `go2_with_lidar.xacro`, a thin wrapper that composes the upstream `robot.xacro` with `lidar_ign.xacro` without patching any upstream files.

### IMU Integration Notes

Fortress publishes the IMU with a scoped frame_id (`go2/base_link/imu_sensor`) that does not exist in the URDF TF tree. The bridge is configured to publish the raw data on `/imu_raw`, and the `imu_frame_relay` node (`go2_nav`) republishes it on `/imu/data` with `frame_id=imu_link`, matching the URDF frame that `robot_localization` EKF looks up in TF.

### ros2_control Setup

| Parameter | Value |
|---|---|
| Controller type | `joint_trajectory_controller/JointTrajectoryController` |
| Command interface | `effort` |
| State interfaces | `position`, `velocity` |
| Update rate | 250 Hz |
| Controller name | `joint_group_effort_controller` |

The 12 joints follow the `lf/rf/lh/rh` prefix convention (left-front / right-front / left-hind / right-hind):

```
lf_hip_joint   lf_upper_leg_joint   lf_lower_leg_joint
rf_hip_joint   rf_upper_leg_joint   rf_lower_leg_joint
lh_hip_joint   lh_upper_leg_joint   lh_lower_leg_joint
rh_hip_joint   rh_upper_leg_joint   rh_lower_leg_joint
```

### Gazebo Fortress vs Classic Plugin Names

| What | Classic (upstream) | Fortress (patched) |
|---|---|---|
| ros2_control filename | `libgazebo_ros2_control.so` | `ign_ros2_control-system` |
| ros2_control plugin name | `gazebo_ros2_control` | `ign_ros2_control::IgnitionROS2ControlPlugin` |
| Hardware interface | `gazebo_ros2_control/GazeboSystem` | `ign_ros2_control/IgnitionSystem` |
| LiDAR sensor type | `ray` + Classic plugin | `gpu_lidar` + `ros_ign_bridge` |

`champ_gazebo` (Classic-only package) is excluded from the colcon build via `--packages-ignore`.

---

## Development Workflow

Both `go2_ign_bringup` and `go2_nav` are volume-mounted in the `dev` service — edit on the host, rebuild inside the container:

```bash
# Start dev container
docker compose run --rm dev bash

# Rebuild after editing launch/config/xacro files
cd /overlay_ws
colcon build --symlink-install --packages-select go2_ign_bringup go2_nav
source install/setup.bash

# Launch the simulation
ros2 launch go2_ign_bringup go2_sim.launch.py

# In another shell — run SLAM mapping
ros2 launch go2_nav slam.launch.py
```

### Useful ROS 2 Commands (inside container)

```bash
# Check active topics
ros2 topic list

# Verify sim clock (~1000 Hz) and LiDAR (~10 Hz)
ros2 topic hz /clock
ros2 topic hz /scan

# Check joint states (12 joints)
ros2 topic echo /joint_states --once

# Check active controllers
ros2 control list_controllers

# View full TF tree (should include map → odom → base_footprint → base_link → front_laser)
ros2 run tf2_tools view_frames

# Launch with RViz
ros2 launch go2_ign_bringup go2_sim.launch.py use_rviz:=true
```

---

## Acknowledgements

- [anujjain-dev/unitree-go2-ros2](https://github.com/anujjain-dev/unitree-go2-ros2) — Go2 description, config, and bundled CHAMP for ROS 2
- [chvmp/champ](https://github.com/chvmp/champ) — CHAMP quadruped locomotion framework
- [ros-controls/ros2_control](https://github.com/ros-controls/ros2_control) — Hardware abstraction and controller manager

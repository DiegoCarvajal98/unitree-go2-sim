# Unitree Go2 Simulation — ROS 2 Humble + Gazebo Fortress

A fully containerized simulation of the [Unitree Go2](https://www.unitree.com/go2/) quadruped robot using ROS 2 Humble, Gazebo Fortress (Ignition 6), and the [CHAMP](https://github.com/chvmp/champ) locomotion controller. The robot walks in response to velocity commands, with GPU-accelerated rendering via NVIDIA Docker.

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

Gazebo Fortress opens with the Go2 standing on a ground plane. The CHAMP locomotion controller starts automatically.

---

## Control the Robot

In a second terminal, attach to the running container:

```bash
docker compose exec sim bash
```

Send a velocity command to make the robot walk:

```bash
# Walk forward
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.3}, angular: {z: 0.0}}"

# Turn left
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2}, angular: {z: 0.5}}"

# Stop
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{}"
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
    └── go2_ign_bringup/    # Custom ROS 2 package (Fortress bringup)
        ├── launch/
        │   └── go2_sim.launch.py   # Main launch file
        ├── config/
        │   ├── go2_controllers.yaml  # ros2_control: effort JointTrajectoryController
        │   └── gz_bridge.yaml        # ROS↔Gazebo topic bridge
        └── worlds/
            └── go2_world.sdf         # Gazebo Fortress world
```

> `src/unitree-go2-ros2/` is not tracked in git — it is cloned automatically during the Docker build from [anujjain-dev/unitree-go2-ros2](https://github.com/anujjain-dev/unitree-go2-ros2), which bundles CHAMP, `go2_description`, and `go2_config`.

---

## Architecture

### Docker Stages

The Dockerfile has three stages that build on each other:

**`base`** — Installs ROS 2 Humble, Gazebo Fortress integration packages (`ros-humble-ros-ign-*`, `ros-humble-ign-ros2-control`), clones the upstream `unitree-go2-ros2` monorepo, applies URDF patches, and builds everything at `/go2_ws`.

**`overlay`** — Copies `src/go2_ign_bringup/` into `/overlay_ws` and builds it with both the ROS install and `/go2_ws` sourced.

**`dev`** — Adds a non-root user (`diego`, UID 1000) and is intended for iterative development with the source volume-mounted (no image rebuild needed for launch/config changes).

### Workspace Layout Inside Containers

```
/opt/ros/humble/    — ROS 2 Humble install
/go2_ws/            — upstream CHAMP + go2_description + go2_config
/overlay_ws/        — go2_ign_bringup (custom Fortress bringup)
/entrypoint.sh      — sources all three; sets IGN_GAZEBO_* paths
```

### Launch Sequence

`go2_sim.launch.py` brings up components in this order:

1. `robot_state_publisher` — publishes the Go2 URDF to `/robot_description`
2. Gazebo Fortress — loads `go2_world.sdf`
3. `ros_ign_gazebo create` — spawns the robot model at z=0.35 m
4. `ros_ign_bridge parameter_bridge` — bridges `/clock`, `/tf`, `/imu/data`
5. *(5-second delay)* `joint_states_controller` spawner
6. `joint_group_effort_controller` spawner (after joint_states_controller exits)
7. `champ_bringup` — CHAMP locomotion controller; subscribes to `/cmd_vel`, publishes to `/joint_group_effort_controller/joint_trajectory`
8. RViz2 (optional, disabled by default)

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

The upstream URDF ships with Gazebo Classic plugin names. The Dockerfile patches them with `sed` at build time:

| What | Classic (upstream) | Fortress (patched) |
|---|---|---|
| ros2_control filename | `libgazebo_ros2_control.so` | `ign_ros2_control-system` |
| ros2_control plugin name | `gazebo_ros2_control` | `ign_ros2_control::IgnitionROS2ControlPlugin` |
| Hardware interface | `gazebo_ros2_control/GazeboSystem` | `ign_ros2_control/IgnitionSystem` |

`champ_gazebo` (Classic-only package) is excluded from the colcon build via `--packages-ignore`.

---

## Development Workflow

Use the `dev` service for iterating on `go2_ign_bringup` without rebuilding the image:

```bash
# Start dev container (source is volume-mounted)
docker compose run --rm dev bash

# Inside the container — rebuild after editing launch/config files
cd /overlay_ws
colcon build --symlink-install --packages-select go2_ign_bringup
source install/setup.bash

# Launch from inside dev container
ros2 launch go2_ign_bringup go2_sim.launch.py
```

### Useful ROS 2 Commands (inside container)

```bash
# Check active topics
ros2 topic list

# Verify sim clock is running (~1000 Hz)
ros2 topic hz /clock

# Check joint states (expect 12 joints)
ros2 topic echo /joint_states --once

# Check active controllers
ros2 control list_controllers

# Launch with RViz
ros2 launch go2_ign_bringup go2_sim.launch.py use_rviz:=true
```

---

## Acknowledgements

- [anujjain-dev/unitree-go2-ros2](https://github.com/anujjain-dev/unitree-go2-ros2) — Go2 description, config, and bundled CHAMP for ROS 2
- [chvmp/champ](https://github.com/chvmp/champ) — CHAMP quadruped locomotion framework
- [ros-controls/ros2_control](https://github.com/ros-controls/ros2_control) — Hardware abstraction and controller manager

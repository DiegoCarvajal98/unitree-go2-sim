# Unitree Go2 Simulation — Architecture & Technical Notes

## Overview

A fully containerized simulation of the Unitree Go2 quadruped robot using **ROS 2 Humble**, **Gazebo Fortress (Ignition 6)**, and the **CHAMP** locomotion controller. The stack runs in Docker with GPU passthrough and supports 2D LiDAR-based SLAM and Nav2 autonomous navigation in an industrial warehouse world.

---

## Architecture

### Docker Build Pipeline

Three sequential image stages build the complete environment:

| Stage | Purpose |
|---|---|
| `base` | Installs ROS 2 Humble, Gazebo Fortress integration (`ros-humble-ros-ign-*`, `ros-humble-ign-ros2-control`, Nav2, SLAM Toolbox). Clones `anujjain-dev/unitree-go2-ros2` (CHAMP + `go2_description` + `go2_config`), applies URDF patches (see Problems), and builds the upstream workspace at `/go2_ws`. |
| `overlay` | Copies the two custom packages (`go2_ign_bringup`, `go2_nav`) and builds them at `/overlay_ws` with the full upstream environment sourced. |
| `dev` | Adds a non-root user (UID 1000) and volume-mounts both packages for live host-side editing without rebuilding the image. |

The `dev` container is the daily-use entry point: edit on the host, run `colcon build --symlink-install` inside the container, relaunch.

### Workspace Layout (Inside Container)

```
/opt/ros/humble/    — ROS 2 Humble install
/go2_ws/            — upstream: CHAMP, go2_description, go2_config
/overlay_ws/        — custom: go2_ign_bringup, go2_nav
/entrypoint.sh      — sources all three; sets IGN_GAZEBO_* resource paths
```

### Launch Sequence (`go2_sim.launch.py`)

1. **`robot_state_publisher`** — publishes the Go2 URDF (with LiDAR) on `/robot_description`
2. **Gazebo Fortress** — loads `industrial.sdf` via `ros_ign_gazebo`
3. **`ros_ign_gazebo create`** — spawns the robot at z = 0.35 m
4. **`ros_ign_bridge`** — bridges `/clock`, `/tf`, `/imu_raw`, `/scan_raw` between Gazebo and ROS
5. *(5 s delay)* **`joint_states_controller` spawner** — waits for `controller_manager` to be ready
6. **`joint_group_effort_controller` spawner** — triggered on exit of step 5 via `OnProcessExit`
7. **`champ_bringup`** — CHAMP locomotion: gait generation, state estimation, joint trajectory output
8. **`imu_frame_relay`** — republishes `/imu_raw` → `/imu/data` with `frame_id=imu_link`
9. **`scan_frame_relay`** — republishes `/scan_raw` → `/scan` with `frame_id=front_laser`
10. *(15 s delay)* **RViz2** (optional)

### Key Components

**`go2_ign_bringup`** — Fortress-specific bringup. Contains the main launch file, the `gz_bridge.yaml` topic bridge config, the `go2_with_lidar.xacro` URDF wrapper, the industrial SDF world, and the RViz config.

**`go2_nav`** — Navigation and relay utilities. Contains `scan_frame_relay`, `imu_frame_relay`, `square_trajectory`, SLAM Toolbox config, Nav2 params, launch files, and the saved warehouse map (`maps/industrial_map.*`).

**CHAMP** (`champ_bringup`) — Quadruped locomotion framework. Receives `/cmd_vel`, runs inverse kinematics and gait generation, publishes joint trajectories to `joint_group_effort_controller/joint_trajectory`. Configured with `close_loop_odom=false` and `orientation_from_imu=true` (see Problems).

---

## Technical Decisions

**Effort interface over position** — The upstream `go2_config` targets a physical Go2 that uses torque control. Keeping `effort` as the command interface on `JointTrajectoryController` preserves physical fidelity and avoids retuning CHAMP for a position interface.

**Xacro wrapper instead of patching upstream** — Rather than forking `go2_description`, the LiDAR is added via `go2_with_lidar.xacro`, a thin wrapper that includes the upstream `robot.xacro` unchanged. This keeps the custom diff minimal and makes upstream updates straightforward.

**Frame relay nodes over static transforms** — Gazebo Fortress scopes sensor frame IDs as `{model}/{link}/{sensor_name}`. Publishing a zero static transform between the scoped frame and the URDF frame would mislead TF (implying a physical offset exists). Instead, relay nodes rewrite `header.frame_id` in software, keeping the TF tree topology correct.

**URDF patches in the Dockerfile** — The upstream URDF ships with Gazebo Classic plugin names. Rather than maintaining a separate fork, two `sed` patches are applied during the `base` image build to swap Classic plugin references for Fortress ones. This is fragile but keeps the upstream clone intact.

---

## Problems Encountered

### 1. Gazebo Classic vs Fortress Plugin Naming

The upstream URDF uses Classic plugin names throughout (`libgazebo_ros2_control.so`, `gazebo_ros2_control`, `gazebo_ros2_control/GazeboSystem`). Fortress requires completely different identifiers (`ign_ros2_control-system`, `ign_ros2_control::IgnitionROS2ControlPlugin`, `ign_ros2_control/IgnitionSystem`). These were patched with `sed` in the Dockerfile at build time. The entire `champ_gazebo` package (Classic-only) was excluded from the colcon build via `--packages-ignore`.

### 2. LiDAR Sensor Type and SDF Element Mismatch

Fortress's `gpu_lidar` sensor requires a `<ray>` child element in URDF/Xacro context (not `<lidar>` as the Fortress documentation sometimes implies). The initial implementation used `<lidar>`, which caused the sensor to silently fail. Multiple commits (`Fix LiDAR sensor type`, `Fix gpu_lidar inner element`) were needed to converge on the correct structure.

### 3. Scoped Sensor frame_id in LiDAR Data

`ros_ign_bridge` copies the Ignition-internal frame ID (`go2/base_link/front_laser_sensor`) verbatim into the `LaserScan` header. SLAM Toolbox and Nav2 look up `front_laser` in TF, so this mismatch caused all TF lookups to fail silently. **Fix:** bridge publishes to `/scan_raw`; `scan_frame_relay` rewrites `header.frame_id` to `front_laser` before republishing on `/scan`.

### 4. CHAMP Closed-Loop Odometry Publishing Static Pose

CHAMP's `close_loop_odom` mode was producing a static (always-zero) odometry output, causing the `odom → base_footprint` transform to never update. The robot appeared frozen in TF even while Gazebo showed it walking. **Fix:** `close_loop_odom=false` was set in the CHAMP bringup arguments, falling back to CHAMP's kinematics-based odometry. `orientation_from_imu=true` was also enabled to fuse IMU heading into state estimation.

### 5. IMU frame_id Mismatch with robot_localization EKF

The same Fortress scoping issue that affected the LiDAR also affected the IMU: the bridge published `/imu/data` with `frame_id=go2/base_link/imu_sensor`, which does not exist in the URDF TF tree. The `robot_localization` EKF silently rejected all IMU messages because it could not look up the transform. **Fix:** bridge was reconfigured to publish raw data on `/imu_raw`; the new `imu_frame_relay` node rewrites `header.frame_id` to `imu_link` and republishes on `/imu/data`.

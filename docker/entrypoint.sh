#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

if [ -f /go2_ws/install/setup.bash ]; then
  source /go2_ws/install/setup.bash
fi

if [ -f /overlay_ws/install/setup.bash ]; then
  source /overlay_ws/install/setup.bash
fi

# Gazebo Fortress (Ignition 6) environment
export IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/opt/ros/humble/lib:${IGN_GAZEBO_SYSTEM_PLUGIN_PATH:-}
export IGN_GAZEBO_RESOURCE_PATH=/overlay_ws/install/go2_ign_bringup/share/go2_ign_bringup/worlds:${IGN_GAZEBO_RESOURCE_PATH:-}

export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}

exec "$@"

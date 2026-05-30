#!/bin/bash
set -e

cd "$(dirname "$0")/.."

# Allow Docker container to open windows on host display
xhost +local:docker

echo "Launching Unitree Go2 simulation (Gazebo Fortress + CHAMP)..."
echo "  Press Ctrl+C to stop."
echo ""
echo "In another terminal you can send velocity commands:"
echo "  docker compose exec sim bash"
echo "  ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \\"
echo "    \"{linear: {x: 0.3}, angular: {z: 0.0}}\""
echo ""

docker compose run --rm sim

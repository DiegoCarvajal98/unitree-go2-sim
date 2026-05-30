#!/bin/bash
set -e

cd "$(dirname "$0")/.."

# Allow Docker to use host X11 display
xhost +local:docker

echo "Building base image (ROS 2 + Gazebo Fortress + CHAMP)..."
docker compose build base

echo "Building overlay image (go2_ign_bringup)..."
docker compose build overlay

echo "Building dev image..."
docker compose build dev

echo ""
echo "Build complete."
echo "  Run simulation : ./scripts/run_sim.sh"
echo "  Dev shell      : docker compose run --rm dev bash"

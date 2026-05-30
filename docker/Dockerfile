ARG ROS_DISTRO=humble

###############################################
# Stage 1 – base: ROS 2 Humble + Gazebo Fortress + all apt deps
###############################################
FROM osrf/ros:${ROS_DISTRO}-desktop-full AS base
ARG ROS_DISTRO=humble
ENV ROS_DISTRO=${ROS_DISTRO}
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

# Gazebo Fortress (Ignition 6) + ros2_control + extras
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    python3-pip \
    python3-vcstool \
    python3-rosdep \
    python3-colcon-common-extensions \
    wget \
    curl \
    tmux \
    # Gazebo Fortress ROS 2 integration (Humble uses ros_ign_* naming for Fortress)
    ros-${ROS_DISTRO}-ros-ign-bridge \
    ros-${ROS_DISTRO}-ros-ign-gazebo \
    ros-${ROS_DISTRO}-ros-ign-image \
    # ros2_control with Ignition Fortress backend
    ros-${ROS_DISTRO}-ign-ros2-control \
    ros-${ROS_DISTRO}-ros2-control \
    ros-${ROS_DISTRO}-ros2-controllers \
    ros-${ROS_DISTRO}-controller-manager \
    ros-${ROS_DISTRO}-joint-state-broadcaster \
    ros-${ROS_DISTRO}-joint-trajectory-controller \
    # Robot description tooling
    ros-${ROS_DISTRO}-robot-state-publisher \
    ros-${ROS_DISTRO}-xacro \
    ros-${ROS_DISTRO}-tf2-ros \
    ros-${ROS_DISTRO}-tf2-tools \
    ros-${ROS_DISTRO}-rviz2 \
    # Teleop & Nav
    ros-${ROS_DISTRO}-teleop-twist-keyboard \
    ros-${ROS_DISTRO}-twist-mux \
    ros-${ROS_DISTRO}-nav2-bringup \
    ros-${ROS_DISTRO}-joy \
    ros-${ROS_DISTRO}-robot-localization \
    && rm -rf /var/lib/apt/lists/*

# Build workspace: CHAMP + Go2 description/config
RUN mkdir -p /go2_ws/src
WORKDIR /go2_ws/src

RUN git clone --depth 1 https://github.com/anujjain-dev/unitree-go2-ros2.git

# Patch go2_description URDF to use Gazebo Fortress (ign_ros2_control) plugins
# instead of Gazebo Classic (gazebo_ros2_control) plugins.
# Critical: without this the ros2_control hardware interface won't load in Fortress.
RUN sed -i \
      's|filename="libgazebo_ros2_control.so"|filename="ign_ros2_control-system"|g' \
      /go2_ws/src/unitree-go2-ros2/robots/descriptions/go2_description/xacro/gazebo.xacro && \
    sed -i \
      's|name="gazebo_ros2_control"|name="ign_ros2_control::IgnitionROS2ControlPlugin"|g' \
      /go2_ws/src/unitree-go2-ros2/robots/descriptions/go2_description/xacro/gazebo.xacro && \
    sed -i \
      's|gazebo_ros2_control/GazeboSystem|ign_ros2_control/IgnitionSystem|g' \
      /go2_ws/src/unitree-go2-ros2/robots/descriptions/go2_description/xacro/leg.xacro

WORKDIR /go2_ws

RUN source /opt/ros/${ROS_DISTRO}/setup.bash && \
    rosdep update && \
    rosdep install --from-paths src --ignore-src --rosdistro ${ROS_DISTRO} -y \
      --skip-keys "ignition-fortress gz-sim7 joint_state_publisher joint_state_publisher_gui" || true

RUN source /opt/ros/${ROS_DISTRO}/setup.bash && \
    colcon build \
      --symlink-install \
      --cmake-args -DCMAKE_BUILD_TYPE=Release \
      --packages-ignore go2_ign_bringup champ_gazebo

###############################################
# Stage 2 – overlay: custom go2_ign_bringup package
###############################################
FROM base AS overlay

RUN mkdir -p /overlay_ws/src
WORKDIR /overlay_ws

COPY src/go2_ign_bringup/ /overlay_ws/src/go2_ign_bringup/
COPY src/go2_nav/        /overlay_ws/src/go2_nav/

RUN source /opt/ros/${ROS_DISTRO}/setup.bash && \
    source /go2_ws/install/setup.bash && \
    colcon build \
      --symlink-install \
      --cmake-args -DCMAKE_BUILD_TYPE=Release

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]

###############################################
# Stage 3 – dev: user account for volume-mounted development
###############################################
FROM overlay AS dev

ARG USERNAME=diego
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

RUN apt-get update && apt-get install -y --no-install-recommends \
    gdb \
    sudo \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid ${USER_GID} ${USERNAME} && \
    useradd --uid ${USER_UID} --gid ${USER_GID} --create-home ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} && \
    chmod 0440 /etc/sudoers.d/${USERNAME}

RUN chown -R ${USER_UID}:${USER_GID} /overlay_ws/ /go2_ws/ && \
    mkdir -p /home/${USERNAME}/.gz && \
    chown -R ${USER_UID}:${USER_GID} /home/${USERNAME}

USER ${USERNAME}
RUN echo "source /entrypoint.sh" >> /home/${USERNAME}/.bashrc

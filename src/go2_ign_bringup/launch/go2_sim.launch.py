import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    RegisterEventHandler,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_bringup = get_package_share_directory('go2_ign_bringup')
    pkg_config = get_package_share_directory('go2_config')
    pkg_champ_bringup = get_package_share_directory('champ_bringup')
    pkg_description = get_package_share_directory('go2_description')
    # ros_ign_gazebo is the Humble/Fortress naming (not ros_gz_sim which is Garden+)
    pkg_ros_ign_gazebo = get_package_share_directory('ros_ign_gazebo')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    use_rviz = LaunchConfiguration('use_rviz', default='false')
    world_file = LaunchConfiguration(
        'world_file',
        default=os.path.join(pkg_bringup, 'worlds', 'industrial.sdf'),
    )

    # Wrapper xacro: upstream robot.xacro + Fortress 2D LiDAR (lidar_ign.xacro)
    robot_description = ParameterValue(
        Command([
            FindExecutable(name='xacro'), ' ',
            os.path.join(pkg_bringup, 'xacro', 'go2_with_lidar.xacro'),
        ]),
        value_type=str,
    )

    rviz_config_path = os.path.join(pkg_bringup, 'rviz', 'go2.rviz')

    # ── Robot State Publisher ─────────────────────────────────
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': use_sim_time,
        }],
    )

    # ── Gazebo Fortress ───────────────────────────────────────
    # For ROS 2 Humble + Fortress the launch file lives in ros_ign_gazebo
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_ign_gazebo, 'launch', 'ign_gazebo.launch.py')
        ),
        launch_arguments={
            'ign_args': ['-r -v 3 ', world_file],
        }.items(),
    )

    # ── Spawn robot into Gazebo Fortress ─────────────────────
    # ros_ign_gazebo provides the 'create' executable for Fortress
    spawn_robot = Node(
        package='ros_ign_gazebo',
        executable='create',
        name='spawn_go2',
        arguments=[
            '-name', 'go2',
            '-topic', 'robot_description',
            '-x', '0.0',
            '-y', '0.0',
            '-z', '0.35',
            '-R', '0.0',
            '-P', '0.0',
            '-Y', '0.0',
        ],
        output='screen',
    )

    # ── ROS <-> Gazebo bridge ─────────────────────────────────
    # ros_ign_bridge is the Humble/Fortress naming
    gz_bridge = Node(
        package='ros_ign_bridge',
        executable='parameter_bridge',
        name='ros_ign_bridge',
        arguments=['--ros-args', '-p',
                   f'config_file:={os.path.join(pkg_bringup, "config", "gz_bridge.yaml")}'],
        output='screen',
    )

    # ── ros2_control: spawn joint_states_controller ───────────
    joint_states_controller = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'joint_states_controller',
            '--controller-manager', '/controller_manager',
        ],
        output='screen',
    )

    # ── ros2_control: spawn effort controller ────────────────
    effort_controller = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'joint_group_effort_controller',
            '--controller-manager', '/controller_manager',
        ],
        output='screen',
    )

    # Spawn effort controller after joint_states_controller is running
    spawn_effort_after_jsb = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=joint_states_controller,
            on_exit=[effort_controller],
        )
    )

    # Give Gazebo + controller_manager time to initialise before spawning controllers
    delayed_controllers = TimerAction(
        period=5.0,
        actions=[joint_states_controller],
    )

    # ── CHAMP locomotion controller ───────────────────────────
    # champ_bringup handles the gait generation and CHAMP state estimation.
    # It publishes joint trajectories to joint_group_effort_controller/joint_trajectory.
    champ_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_champ_bringup, 'launch', 'bringup.launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'robot_name': 'go2',
            'gazebo': 'true',
            'hardware_connected': 'false',
            'publish_foot_contacts': 'true',
            'close_loop_odom': 'true',
            'joint_controller_topic': 'joint_group_effort_controller/joint_trajectory',
            'joints_map_path': os.path.join(pkg_config, 'config', 'joints', 'joints.yaml'),
            'links_map_path': os.path.join(pkg_config, 'config', 'links', 'links.yaml'),
            'gait_config_path': os.path.join(pkg_config, 'config', 'gait', 'gait.yaml'),
            'description_path': os.path.join(pkg_description, 'xacro', 'robot.xacro'),
        }.items(),
    )

    # ── Static TF: bridge Ignition sensor frame to URDF frame ────
    # Fortress names the sensor frame "go2/base_link/front_laser_sensor"
    # (scoped from the model). SLAM/Nav2 expect the URDF frame "front_laser".
    lidar_frame_bridge = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='lidar_frame_bridge',
        arguments=['0', '0', '0', '0', '0', '0',
                   'front_laser', 'go2/base_link/front_laser_sensor'],
        output='screen',
    )

    # ── RViz2 (optional, delayed so Gazebo finishes loading first) ──
    rviz = TimerAction(
        period=10.0,
        actions=[Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            parameters=[{'use_sim_time': use_sim_time}],
            condition=IfCondition(use_rviz),
            output='screen',
            arguments=['-d', rviz_config_path],
        )],
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true',
                              description='Use /clock from Gazebo'),
        DeclareLaunchArgument('use_rviz', default_value='false',
                              description='Launch RViz2'),
        DeclareLaunchArgument('world_file',
                              default_value=os.path.join(
                                  pkg_bringup, 'worlds', 'industrial.sdf'),
                              description='Path to Gazebo Fortress .sdf world'),
        robot_state_publisher,
        gazebo,
        spawn_robot,
        gz_bridge,
        delayed_controllers,
        spawn_effort_after_jsb,
        champ_bringup,
        lidar_frame_bridge,
        rviz,
    ])

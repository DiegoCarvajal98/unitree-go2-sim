import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_nav = get_package_share_directory('go2_nav')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    slam_params = LaunchConfiguration(
        'slam_params',
        default=os.path.join(pkg_nav, 'config', 'slam_params.yaml'),
    )

    slam_toolbox = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[slam_params, {'use_sim_time': use_sim_time}],
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true',
                              description='Use simulation clock'),
        DeclareLaunchArgument('slam_params',
                              default_value=os.path.join(
                                  pkg_nav, 'config', 'slam_params.yaml'),
                              description='Path to slam_toolbox params YAML'),
        slam_toolbox,
    ])

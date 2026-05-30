from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('side_length',   default_value='1.0',   description='Side length in metres'),
        DeclareLaunchArgument('linear_speed',  default_value='0.25',  description='Forward speed in m/s'),
        DeclareLaunchArgument('angular_speed', default_value='0.5',   description='Turn speed in rad/s'),
        DeclareLaunchArgument('loop',          default_value='false',  description='Repeat the square indefinitely'),

        Node(
            package='go2_nav',
            executable='square_trajectory',
            name='square_trajectory',
            output='screen',
            parameters=[{
                'side_length':   LaunchConfiguration('side_length'),
                'linear_speed':  LaunchConfiguration('linear_speed'),
                'angular_speed': LaunchConfiguration('angular_speed'),
                'loop':          LaunchConfiguration('loop'),
            }],
        ),
    ])

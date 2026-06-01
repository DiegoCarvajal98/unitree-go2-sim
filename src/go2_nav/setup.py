from glob import glob
import os
from setuptools import setup

package_name = 'go2_nav'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Diego Carvajal',
    maintainer_email='diego98cs@gmail.com',
    description='Navigation nodes for the Unitree Go2 simulation',
    license='MIT',
    entry_points={
        'console_scripts': [
            'square_trajectory = go2_nav.square_trajectory:main',
            'scan_frame_relay = go2_nav.scan_frame_relay:main',
            'imu_frame_relay = go2_nav.imu_frame_relay:main',
        ],
    },
)

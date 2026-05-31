cmake_minimum_required(VERSION 3.8)
project(go2_ign_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch worlds config xacro rviz
  DESTINATION share/${PROJECT_NAME}
)

ament_package()

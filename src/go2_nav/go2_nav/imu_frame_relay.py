import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu


class ImuFrameRelay(Node):
    """
    Republishes /imu_raw with the Ignition-scoped frame_id
    (go2/base_link/imu_sensor) as /imu/data with frame_id=imu_link
    so the robot_localization EKF can look it up in TF.
    """

    def __init__(self):
        super().__init__('imu_frame_relay')

        self.declare_parameter('input_topic', '/imu_raw')
        self.declare_parameter('output_topic', '/imu/data')
        self.declare_parameter('output_frame', 'imu_link')

        in_topic  = self.get_parameter('input_topic').value
        out_topic = self.get_parameter('output_topic').value
        self._frame = self.get_parameter('output_frame').value

        self._pub = self.create_publisher(Imu, out_topic, 10)
        self.create_subscription(Imu, in_topic, self._cb, 10)

        self.get_logger().info(
            f'Relaying {in_topic} → {out_topic} with frame_id={self._frame}'
        )

    def _cb(self, msg: Imu):
        msg.header.frame_id = self._frame
        self._pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ImuFrameRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

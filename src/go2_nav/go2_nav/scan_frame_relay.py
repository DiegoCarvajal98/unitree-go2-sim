import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class ScanFrameRelay(Node):
    """
    Subscribes to /scan_raw (Ignition-bridged scan with scoped frame_id like
    'go2/base_link/front_laser_sensor') and republishes to /scan with the
    URDF frame_id 'front_laser' so SLAM and Nav2 can look it up in TF.
    """

    def __init__(self):
        super().__init__('scan_frame_relay')

        self.declare_parameter('input_topic', '/scan_raw')
        self.declare_parameter('output_topic', '/scan')
        self.declare_parameter('output_frame', 'front_laser')

        in_topic  = self.get_parameter('input_topic').value
        out_topic = self.get_parameter('output_topic').value
        self._frame = self.get_parameter('output_frame').value

        self._pub = self.create_publisher(LaserScan, out_topic, 10)
        self.create_subscription(LaserScan, in_topic, self._cb, 10)

        self.get_logger().info(
            f'Relaying {in_topic} → {out_topic} with frame_id={self._frame}'
        )

    def _cb(self, msg: LaserScan):
        msg.header.frame_id = self._frame
        self._pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ScanFrameRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

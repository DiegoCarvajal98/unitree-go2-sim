import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class SquareTrajectory(Node):
    """Drive the robot in a square by timing forward and turning phases."""

    def __init__(self):
        super().__init__('square_trajectory')

        self.declare_parameter('side_length', 1.0)    # metres
        self.declare_parameter('linear_speed', 0.25)  # m/s
        self.declare_parameter('angular_speed', 0.5)  # rad/s
        self.declare_parameter('loop', False)

        side = self.get_parameter('side_length').value
        v    = self.get_parameter('linear_speed').value
        w    = self.get_parameter('angular_speed').value
        self.loop = self.get_parameter('loop').value

        self._side_duration = side / v
        self._turn_duration = (math.pi / 2.0) / w
        self._v = v
        self._w = w

        self._pub   = self.create_publisher(Twist, 'cmd_vel', 10)
        self._state = 'FORWARD'
        self._sides_done = 0
        self._t0    = self.get_clock().now()

        self.create_timer(0.05, self._tick)  # 20 Hz

        self.get_logger().info(
            f'Square trajectory started  side={side:.2f} m  '
            f'v={v:.2f} m/s  w={w:.2f} rad/s  loop={self.loop}'
        )

    # ------------------------------------------------------------------ #

    def _tick(self):
        elapsed = (self.get_clock().now() - self._t0).nanoseconds * 1e-9
        msg = Twist()

        if self._state == 'FORWARD':
            if elapsed < self._side_duration:
                msg.linear.x = self._v
            else:
                self._enter('TURNING')
                return

        elif self._state == 'TURNING':
            if elapsed < self._turn_duration:
                msg.angular.z = self._w
            else:
                self._sides_done += 1
                if self._sides_done >= 4:
                    if self.loop:
                        self._sides_done = 0
                        self.get_logger().info('Square complete — looping')
                        self._enter('FORWARD')
                    else:
                        self.get_logger().info('Square trajectory complete')
                        self._pub.publish(Twist())
                        raise SystemExit
                    return
                self._enter('FORWARD')
                return

        self._pub.publish(msg)

    def _enter(self, state: str):
        self._state = state
        self._t0 = self.get_clock().now()


# ------------------------------------------------------------------ #

def main(args=None):
    rclpy.init(args=args)
    node = SquareTrajectory()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    node._pub.publish(Twist())  # stop robot on exit
    node.destroy_node()
    rclpy.shutdown()

#!/usr/bin/env python3
"""
odom_timestamp_relay.py

Fixes hardware clock vs system clock mismatch between point_lio and RTABMap.

point_lio publishes /aft_mapped_to_init at ~200Hz with LiDAR hardware clock.
RTABMap approx_sync cannot match 200Hz odom with 10Hz Kinect images.

This node:
  1. Caches the latest odom from point_lio
  2. Republishes /odom at 10Hz (matching Kinect) with system clock timestamp
  3. Publishes TF odom->base_link at 10Hz with system clock timestamp
  4. Republishes /unilidar/cloud on /unilidar/cloud_synced with system clock

10Hz matches the Kinect frame rate so approx_sync can easily match all three.
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster


class OdomTimestampRelay(Node):

    def __init__(self):
        super().__init__('odom_timestamp_relay')

        # Cache latest odom from point_lio
        self.latest_odom = None

        # Subscribe to point_lio high-rate hardware-clock odom
        self.odom_sub = self.create_subscription(
            Odometry,
            '/aft_mapped_to_init',
            self.odom_callback,
            10
        )

        # Publish corrected odom at 10Hz to match Kinect frame rate
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.timer = self.create_timer(0.1, self.publish_odom)  # 10Hz

        # LiDAR cloud: restamp and republish
        self.cloud_sub = self.create_subscription(
            PointCloud2,
            '/unilidar/cloud',
            self.cloud_callback,
            10
        )
        self.cloud_pub = self.create_publisher(
            PointCloud2, '/unilidar/cloud_synced', 10)

        self.get_logger().info(
            'odom_timestamp_relay started:\n'
            '  /aft_mapped_to_init cached, republished on /odom at 10Hz\n'
            '  TF odom->base_link published at 10Hz\n'
            '  /unilidar/cloud -> /unilidar/cloud_synced (system clock)'
        )

    def odom_callback(self, msg):
        # Just cache - do not republish here
        self.latest_odom = msg

    def publish_odom(self):
        # Called at 10Hz by timer
        if self.latest_odom is None:
            return

        now = self.get_clock().now().to_msg()
        msg = self.latest_odom

        # Publish corrected /odom
        msg.header.stamp = now
        msg.header.frame_id = 'odom'
        msg.child_frame_id = 'base_link'
        self.odom_pub.publish(msg)

        # Publish corrected TF odom->base_link
        t = TransformStamped()
        t.header.stamp = now
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = msg.pose.pose.position.x
        t.transform.translation.y = msg.pose.pose.position.y
        t.transform.translation.z = msg.pose.pose.position.z
        t.transform.rotation = msg.pose.pose.orientation
        self.tf_broadcaster.sendTransform(t)

    def cloud_callback(self, msg):
        msg.header.stamp = self.get_clock().now().to_msg()
        self.cloud_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = OdomTimestampRelay()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

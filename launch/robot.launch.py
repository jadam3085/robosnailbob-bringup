import os

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

from ament_index_python.packages import get_package_share_directory
from launch.substitutions import Command


def generate_launch_description():

    pkg_path = get_package_share_directory('robot_bringup')
    xacro_file = os.path.join(pkg_path, 'urdf', 'tank_robot.xacro')
    rviz_file  = os.path.join(pkg_path, 'rviz', 'robot.rviz')

    robot_description = ParameterValue(
        Command(['xacro ', xacro_file]),
        value_type=str
    )

    return LaunchDescription([

        # ROBOT STATE PUBLISHER
        # Publishes TFs for all frames defined in the XACRO:
        # base_link, wheels, kinect_link (visual only), lidar_link,
        # unilidar_lidar, unilidar_imu.
        # Does NOT publish any kinect2_* frames - those belong to kinect2_bridge.
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_description}],
            output='screen'
        ),

        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            output='screen'
        ),

        # STATIC TFs
        # kinect2_link: this is the bridge between our robot body and the
        # kinect2_bridge TF tree. kinect2_bridge publishes all frames FROM
        # kinect2_link downward. We publish base_link -> kinect2_link here.
        # The rotation -1.5708 0 4.71239 was confirmed working in first session.
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='kinect_tf',
            arguments=[
                '0.15', '0.0', '0.35',
                '-1.5708', '0', '4.71239',
                'base_link', 'kinect2_link'
            ]
        ),

        # unilidar_lidar: the Unitree driver publishes the pointcloud in this
        # frame. robot_state_publisher handles base_link -> lidar_link ->
        # unilidar_lidar from the XACRO, so this static TF is belt-and-suspenders
        # in case of timing issues at startup.
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='lidar_tf',
            arguments=[
                '0.15', '0.0', '0.5',
                '0', '0', '0',
                'base_link', 'unilidar_lidar'
            ]
        ),

        # KINECT v2
        # kinect2_bridge publishes_tf: true so it owns kinect2_link and all
        # child optical frames using its internal calibration data.
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(
                os.path.join(
                    get_package_share_directory('kinect2_bridge'),
                    'launch',
                    'kinect2_bridge_launch.yaml'
                )
            )
        ),

        # UNITREE L1 LiDAR
        # launch.py is installed at the share root, not in a launch/ subdir.
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(
                os.path.join(
                    get_package_share_directory('unitree_lidar_ros2'),
                    'launch.py'
                )
            )
        ),

        # RGBD SYNC
        Node(
            package='rtabmap_sync',
            executable='rgbd_sync',
            output='screen',
            parameters=[{
                'approx_sync':     True,
                'sync_queue_size': 30
            }],
            remappings=[
                ('rgb/image',       '/kinect2/qhd/image_color_rect'),
                ('depth/image',     '/kinect2/qhd/image_depth_rect'),
                ('rgb/camera_info', '/kinect2/qhd/camera_info'),
                ('rgbd_image',      '/rgbd_image')
            ]
        ),

        # RGBD ODOMETRY
        # Sole publisher of odom -> base_link TF.
        Node(
            package='rtabmap_odom',
            executable='rgbd_odometry',
            output='screen',
            parameters=[{
                'frame_id':         'base_link',
                'odom_frame_id':    'odom',
                'publish_tf':       True,
                'approx_sync':      True,
                'subscribe_rgbd':   True,
                'wait_imu_to_init': False
            }],
            remappings=[
                ('rgbd_image', '/rgbd_image')
            ]
        ),

        # RTABMAP SLAM
        Node(
            package='rtabmap_slam',
            executable='rtabmap',
            output='screen',
            parameters=[{
                'frame_id':               'base_link',
                'subscribe_rgbd':         True,
                'subscribe_scan_cloud':   True,
                'approx_sync':            True,
                'Mem/IncrementalMemory':  'true',
                'Mem/InitWMWithAllNodes': 'false'
            }],
            remappings=[
                ('rgbd_image', '/rgbd_image'),
                ('scan_cloud', '/unilidar/cloud'),
                ('odom',       '/odom')
            ]
        ),

        # RTABMAP VIZ
        Node(
            package='rtabmap_viz',
            executable='rtabmap_viz',
            output='screen',
            parameters=[{
                'subscribe_rgbd':       True,
                'subscribe_scan_cloud': True,
                'approx_sync':          True
            }],
            remappings=[
                ('rgbd_image', '/rgbd_image'),
                ('scan_cloud', '/unilidar/cloud'),
                ('odom',       '/odom')
            ]
        ),

        # RVIZ2
        TimerAction(
            period=5.0,
            actions=[
                Node(
                    package='rviz2',
                    executable='rviz2',
                    arguments=['-d', rviz_file],
                    output='screen'
                )
            ]
        )
    ])

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

    point_lio_config = os.path.join(
        get_package_share_directory('point_lio'),
        'config', 'unilidar_l1.yaml'
    )

    return LaunchDescription([

        # ROBOT STATE PUBLISHER
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

        # STATIC TFs - confirmed working values, unchanged
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

        # KINECT v2 - unchanged
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(
                os.path.join(
                    get_package_share_directory('kinect2_bridge'),
                    'launch',
                    'kinect2_bridge_launch.yaml'
                )
            )
        ),

        # UNITREE L1 LiDAR - unchanged
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(
                os.path.join(
                    get_package_share_directory('unitree_lidar_ros2'),
                    'launch.py'
                )
            )
        ),

        # POINT-LIO
        # Uses internal frame names 'lio_odom' and 'lio_base' so its
        # own TF broadcasts (which carry LiDAR hardware timestamps) do
        # NOT write to the odom->base_link transform that RTABMap reads.
        # The relay node below is the SOLE publisher of odom->base_link.
        Node(
            package='point_lio',
            executable='pointlio_mapping',
            name='point_lio',
            output='screen',
            parameters=[
                point_lio_config,
                {
                    'odom_header_frame_id':   'lio_odom',
                    'odom_child_frame_id':    'lio_base',
                    'use_imu_as_input':       False,
                    'prop_at_freq_of_imu':    True,
                    'check_satu':             True,
                    'init_map_size':          10,
                    'point_filter_num':       1,
                    'space_down_sample':      True,
                    'filter_size_surf':       0.1,
                    'filter_size_map':        0.1,
                    'cube_side_length':       1000.0,
                    'runtime_pos_log_enable': False,
                }
            ]
        ),

        # ODOM TIMESTAMP RELAY
        # - Subscribes to /aft_mapped_to_init (hardware-clock timestamps)
        # - Republishes on /odom with system clock timestamp
        # - Also publishes TF odom->base_link with system clock timestamp
        # This is the ONLY source of odom->base_link TF.
        # point_lio publishes lio_odom->lio_base TF which does not conflict.
        Node(
            package='robot_bringup',
            executable='odom_timestamp_relay.py',
            name='odom_timestamp_relay',
            output='screen'
        ),

        # RGBD SYNC - unchanged
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

        # RTABMAP SLAM - unchanged
        Node(
            package='rtabmap_slam',
            executable='rtabmap',
            output='screen',
            parameters=[{
                'frame_id':               'base_link',
                'subscribe_rgbd':         True,
                'subscribe_scan_cloud':   True,
                'approx_sync':            True,
                'sync_queue_size':        30,
                'Mem/IncrementalMemory':  'true',
                'Mem/InitWMWithAllNodes': 'false',
            }],
            remappings=[
                ('rgbd_image', '/rgbd_image'),
                ('scan_cloud', '/unilidar/cloud'),
                ('odom',       '/odom')
            ]
        ),

        # RTABMAP VIZ - unchanged
        Node(
            package='rtabmap_viz',
            executable='rtabmap_viz',
            output='screen',
            parameters=[{
                'subscribe_rgbd':       True,
                'subscribe_scan_cloud': True,
                'approx_sync':          True,
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

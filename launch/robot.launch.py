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

        # Kinect TF only - lidar TF comes solely from XACRO
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

        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(
                os.path.join(
                    get_package_share_directory('kinect2_bridge'),
                    'launch',
                    'kinect2_bridge_launch.yaml'
                )
            )
        ),

        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(
                os.path.join(
                    get_package_share_directory('unitree_lidar_ros2'),
                    'launch.py'
                )
            )
        ),

        Node(
            package='rtabmap_odom',
            executable='icp_odometry',
            output='screen',
            parameters=[{
                'frame_id':                      'base_link',
                'odom_frame_id':                 'odom',
                'publish_tf':                    True,
                'wait_imu_to_init':              True,
                'approx_sync':                   True,
                'queue_size':                    10,
                'Icp/PointToPlaneK':             '20',
                'Icp/PointToPlaneRadius':        '0',
                'Icp/MaxCorrespondenceDistance': '1.0',
                'Icp/VoxelSize':                 '0.1',
                'Icp/Epsilon':                   '0.001',
                'Icp/MaxTranslation':            '2.0',
                'Icp/PM':                        True,
                'Icp/PMOutlierRatio':            '0.7',
                'OdomF2M/ScanSubtractRadius':    '0.1',
                'OdomF2M/ScanMaxSize':           '15000',
                'Optimizer/GravitySigma':        '0.3',
            }],
            remappings=[
                ('scan_cloud', '/unilidar/cloud'),
                ('imu',        '/unilidar/imu'),
            ]
        ),

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

        Node(
            package='rtabmap_slam',
            executable='rtabmap',
            output='screen',
            parameters=[{
                'frame_id':                              'base_link',
                'subscribe_rgbd':                        True,
                'subscribe_scan_cloud':                  True,
                'approx_sync':                           True,
                'sync_queue_size':                       30,
                'Mem/IncrementalMemory':                 'true',
                'Mem/InitWMWithAllNodes':                'false',
                'RGBD/LinearUpdate':                     '0.1',
                'RGBD/AngularUpdate':                    '0.1',
                'map_always_update':                     True,
                'cloud_subtract_filtering':              True,
                'cloud_subtract_filtering_min_neighbors': 2,
            }],
            remappings=[
                ('rgbd_image', '/rgbd_image'),
                ('scan_cloud', '/unilidar/cloud'),
                ('imu',        '/unilidar/imu'),
                ('odom',       '/odom')
            ]
        ),

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

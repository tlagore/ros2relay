from setuptools import setup

package_name = 'ros2relay'

setup(
    name=package_name,
    version='0.0.0',
    packages=[
        package_name,
        'ros2relay.message_socket'
    ],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Tyrone Lagore',
    maintainer_email='tyrone@gmail.com',
    description='Simple relay that subscribes to ros topics and relays them to remote endpoints',
    license='Apache 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'net_publisher = ros2relay.network_publisher:main',
            'net_subscriber = ros2relay.network_subscriber:main',
            'simple_publisher = ros2relay.simple_publisher:main',
        ],
    },
)

# ros2relay
ros2relay allows for cross network publishing of ros2 topics. This is my first attempt at ros programming, so there's probably a bunch of typical paradigm breaking.

## design
ros2relay implements two primary nodes:

### net_publisher
net_publisher subscribes to a set of local topics defined by params.yml. It then relays any messages that it observes to a remote host/port as defined by the `server` and `port` parameter.

### net_subscriber
net_subscriber "subscribes" to the net_publisher by simply listening on the same port. When it receives a message, it publishes it locally on the same topic.

# parameters
both net_publisher and net_subscriber rely on a set of parameters and (currently) must be set by a parameters file. With this early version, they will crash on startup without setting the parameters (it does not implement default parameters yet).

## synchronized parameters
**synchronized parameters must be the same between communicating nodes, they are not synchronized automatically (yet), you must set these to be the same**

`topics` : these define a list of topic names to which the publisher/subscriber should support as they are emitted on the local network

`topicTypes` : these define the type of each topic and must have a 1-1 mapping with the `topics` parameter. (for example std_mdsgs.msg.String). **Currently only built in messages are supported. Custom messages are not supported but thinking about adding them** 

`port` : the port to communicate on

`mode` : udp or tcp (lower case currently, will remove case sensitivity later). Use tcp if you don't want to miss any messages. Use udp if speed is preferred to message stream quality.

## net_publisher specific parameters
`server` : The address of the remote endpoint to relay topic information to

## net_subscriber specific parameters
`num_listeners` : only applies when mode=udp. The number of threads to handle messages. Increase this value if you have a lot of topic traffic. Too high and you'll start exhausting resources - there is no cap on num_listeners so increase at your own risk.

*example config*
```
ros2relay_net_publisher:
    ros__parameters:
        topics: ['topic_num', 'topic']
        topicTypes: ['std_msgs.msg.Int64', 'std_msgs.msg.String']
        port: 12499
        mode: "udp"
        server: "192.168.0.51"
ros2relay_net_subscriber:
    ros__parameters:
        topics: ['topic', 'topic_num']
        topicTypes: ['std_msgs.msg.String', 'std_msgs.msg.Int64']
        mode: "udp"
        port: 12499
        num_listeners: 5
```

**Note above:** net_publisher inverts how it declares topics/topicTypes, but they still line up properly (`topic_num` is of type `std_msgs.msg.Int64` and `topic` is of type `std_msgs.msg.String`)

# Usage
**Enter your working directory, for example (if your workspace was `~\dev_ws`)**

`cd ~\dev_ws\src`

**Clone the repository**

`git clone https://github.com/tlagore/ros2relay.git`

**Edit the parameter file for your desired topics (you can change other parameters at this point too if you want)**

You can manually add the "exec_depends" in your package.xml, or you can use the gen.py script in the repo:

```
cd ~\dev_ws\src\ros2relay
python3 gen.py
```

The above will read in your params.yml file and look at your topicTypes variable, adding each of these as exec_depends to your package.xml

**Build ros2relay**

`cd ~\dev_ws`

`colcon build --packages-select ros2relay`


**source setup**
`. install\setup.bash`

**run net_subscriber on endpoint where you want to send the node data**
`ros2 run ros2relay net_subscriber __params:=src\ros2relay\params.yml`

**run net_publisher on endpoint where you are locally emitting the data**
`ros2 run ros2relay net_publisher __params:=src\ros2relay\params.yml`

Feel free to separate out the parameters to their own files, I found it easier to keep them in the same file.

Please note I am not actively updating this package, but will add features as I need them for my own purposes. Feel free to fork and add your own stuff to it.
import xml.etree.ElementTree as ET
from xml.dom import minidom
import yaml

def main(args=None):
    """ """
    required = ['rclpy']
    tree = ET.parse("package.xml")
    root = tree.getroot()
    #actual elements
    exec_depends = [el for el in root if el.tag == 'exec_depend']
    #just text
    exec_depends_inner = [el.tag for el in exec_depends]

    to_remove = [ depend for depend in exec_depends if depend not in required ]

    # clean up unknown exec_depends - note any dependencies read from params.yml will be readded
    for el in to_remove:
        root.remove(el)

    with open("params.yml", 'r') as stream:
        try:
            appended = []
            changed = False
            yml_data = yaml.safe_load(stream)
            topicTypes = yml_data['ros2relay_net_publisher']['ros__parameters']['topicTypes']
            for topicType in topicTypes:
                lib = topicType.split('.')[0]
                if lib is not None:
                    if lib not in exec_depends_inner and lib not in appended:
                        print(f'Parsed {topicType}, not found in exec_depends. Adding {lib}.')
                        newEl = ET.Element('exec_depend')
                        newEl.text = lib
                        root.append(newEl)
                        changed = True
                        appended += [lib]
            
            if changed:
                # ET.tostring has a lot of extra new lines, custom pretty print
                pretty_print = '\n'.join([line for line in minidom.parseString(ET.tostring(root)).toprettyxml(indent=' '*2).split('\n') if line.strip()])
                with open("package.xml", "w") as f:
                    f.write(pretty_print)

        except yaml.YAMLError as exc:
            print(exc)

if __name__ == '__main__':
    main()
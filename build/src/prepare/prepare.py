import os
import pathlib
import yaml

import xml.etree.ElementTree as ET

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Main thing here - we're using jinja2_time.TimeExtension (https://github.com/hackebrot/jinja2-time)
env = Environment(
    loader=FileSystemLoader("/opt/input"),
    autoescape=select_autoescape(["xml"]),
    extensions=['jinja2_time.TimeExtension'],
)
env.datetime_format = "%Y-%m-%d %T"

def scenario_from_template(scenario_name, config):
    '''
    Function to make valid XML from Jinja2 template
    '''
    scenario_file_path = "/opt/input/{}".format(scenario_name)

    if not os.path.exists(scenario_file_path):
        scenario_file_path += ".xml"
        if not os.path.exists(scenario_file_path):
            return

    if not scenario_file_path.endswith(".xml"):
        return

    with open(r'{}'.format(scenario_file_path)) as template_file:
        template = env.from_string(template_file.read())
    result_scenario = template.render(c=config["c"], a=config["a"])

    return result_scenario


def separate_scenario(scenario, combined_config):
    '''
    Funciton that returns dict of ET.ElementTree XML structures for voip_patrol and database config
    '''

    try:
        root = ET.fromstring(scenario)
    except Exception as e:
        print("Problem processing {} scenario: {}".format(scenario ,e))
        return {}

    if root.tag != 'config':
        print('Root element is not <config> in {}'.format(scenario))
        return {}

    separate_scenarios = {}

    for child in root:

        # For backward compatibility
        if child.tag == 'actions':
            separate_scenarios['voip_patrol'] = ET.ElementTree(root)
            break

        if child.attrib.get('type') == 'voip_patrol':
            separate_scenarios['voip_patrol'] = get_vp_config(child)

        if child.attrib.get('type') == 'database':
            separate_scenarios['database'] = get_database_config(child, combined_config)

    return separate_scenarios


def write_scenarios(name, separate_scenarios):
    '''
    Function to write separate scenarios to /opt/output/<scenario_name>/voip_patrol.xml and /opt/output/<scenario_name>/database.xml
    '''

    # Strip the ".XML"
    scenario_name = name.split(".")[0]
    scenario_dir_path = '/opt/output/{}'.format(scenario_name)
    if not os.path.exists(scenario_dir_path):
        os.mkdir(scenario_dir_path)

    vp_scenario_tree = separate_scenarios.get("voip_patrol")
    if vp_scenario_tree:
        vp_scenario_tree.write("{}/voip_patrol.xml".format(scenario_dir_path))

    db_scenario_tree = separate_scenarios.get("database")
    if db_scenario_tree:
        db_scenario_tree.write("{}/database.xml".format(scenario_dir_path))

def get_vp_config(config):
    '''
    Take an voip_patrol config and make new root - <config> for it
    '''
    if config[0].tag != 'actions':
        raise Exception('Tag is not <actions>')

    root = ET.Element('config')
    root.append(config[0])

    return ET.ElementTree(root)

def get_database_config(config, combined_config):
    '''
    Take a database config and enrich it with additional data so database scenarios will contain also credentials for database
    This data is taken from config.yaml
    '''
    if config[0].tag != 'actions':
        raise Exception('Tag is not <actions>')

    actions = config[0]

    # First - check if we have databases section to enrich
    db_common_config = combined_config.get('d')
    if not db_common_config:
        root = ET.Element('config')
        root.append(actions)

        return ET.ElementTree(root)

    for action in actions:

        db_name = action.attrib.get('database')
        if not db_name:
            continue

        current_db_config = db_common_config.get(db_name)
        if not current_db_config:
            continue

        current_db_info = ET.SubElement(action, 'info')
        for k, v in current_db_config.items():
            current_db_info.attrib[k] = v

    root = ET.Element('config')
    root.append(actions)

    return ET.ElementTree(root)

def process_scenario(name, combined_config):
    '''
    Here we taking template and making valid voip_patrol and database scenarios.
    '''
    print("Processing {}".format(name))

    result_xml = scenario_from_template(name, combined_config)
    if result_xml is None:
        return
    separate_scenarios = separate_scenario(result_xml, combined_config)
    write_scenarios(name, separate_scenarios)


# Main script starting
try:

    print("Starting preparing template(s)...")

    try:
        os.remove('/opt/output/scenarios.done')
    except:
        pass

    with open(r'/opt/input/config.yaml') as config_file:
        print("Reading config.yaml...")
        config = yaml.load(config_file, Loader=yaml.FullLoader)

    # Read main config.yaml and prepare python dicts
    global_config = config.get('global')

    default_domain = global_config.get('domain', '')
    default_transport = global_config.get('transport', 'udp')
    default_srtp = global_config.get('srtp', 'none')

    account_config = config.get('accounts')
    if account_config:
        account_config_mixed = {}
        for key in account_config:
            if not isinstance(key, (int, str)):
                continue

            account_config_mixed[key] = account_config[key]
            account_config_mixed[key]['label'] = key
            account_config_mixed[key]['domain'] = account_config[key].get('domain', default_domain)
            account_config_mixed[key]['transport'] = account_config[key].get('transport', default_transport)
            account_config_mixed[key]['srtp'] = account_config[key].get('srtp', default_srtp)

            # Make sure we can use a.88881 and a['88881'] at the same time. If 88881 is the number ;)
            if type(key) is str and key.isnumeric():
                account_config_mixed[int(key)] = account_config_mixed[key]

    single_scenario = os.environ.get("SCENARIO_NAME")

    combined_config = {
        "a": account_config_mixed,
        "c": global_config,
        "d": config.get('databases'),
    }

    # Walk through the files and create scenarios

    if single_scenario and single_scenario != "":
        single_scenario = single_scenario.split("/")[-1]
        process_scenario(single_scenario, combined_config)
    else:
        for filename in os.listdir('/opt/input'):
            process_scenario(filename, combined_config)

    pathlib.Path('/opt/output/scenarios.done').touch(mode=777)

except Exception as e:
    print("Error preparing: {}".format(e))

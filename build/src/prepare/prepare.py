import os
import pathlib
import yaml

import lxml.etree as ET

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Main thing here - we're using jinja2_time.TimeExtension (https://github.com/hackebrot/jinja2-time)
env = Environment(
    loader=FileSystemLoader("/opt/input"),
    autoescape=select_autoescape(["xml"]),
    extensions=['jinja2_time.TimeExtension'],
)

env.datetime_format = "%Y-%m-%d %T"  # type: ignore (Ignoring as pylance not getting extension of jinja2_time.TimeExtension)

# Scenario processing functions
def scenario_from_template(scenario_name, config):
    '''
    Function to make valid XML from Jinja2 template
    '''
    scenario_file_path = f"/opt/input/{scenario_name}"

    if not os.path.exists(scenario_file_path):
        scenario_file_path += ".xml"
        if not os.path.exists(scenario_file_path):
            return

    if not scenario_file_path.endswith(".xml"):
        return

    with open(r'{}'.format(scenario_file_path)) as template_file:
        template = env.from_string(template_file.read())

    # We're adding scenario (file) name to be accessible in template variables
    current_scenario_name = scenario_name.split(".")[0]

    result_scenario = template.render(c=config["c"], a=config["a"], g=config["c"], d=config["d"], scenario_name=current_scenario_name)

    return result_scenario


def separate_scenario(scenario, combined_config):
    '''
    Funciton that returns dict of ET.ElementTree XML structures for voip_patrol and database config
    '''
    parser = ET.XMLParser(strip_cdata=False, remove_comments=True)

    try:
        root = ET.fromstring(scenario, parser)
    except Exception as e:
        print(f"Problem processing {scenario} scenario: {e}")
        return {}

    if root.tag != 'config':
        print(f"Root element is not <config> in {scenario}")
        return {}

    separate_scenarios = {}

    for child in root:

        # For backward compatibility
        if child.tag == 'actions':
            separate_scenarios['voip_patrol'] = get_vp_config(root)
            break

        if child.attrib.get('type') == 'voip_patrol':
            separate_scenarios['voip_patrol'] = get_vp_config(child)

        if child.attrib.get('type') == 'database':
            separate_scenarios['database'] = get_database_config(child, combined_config)

        if child.attrib.get('type') == 'media_check':
            separate_scenarios['media_check'] = get_generic_config(child)

        if child.attrib.get('type') == 'sipp':
            separate_scenarios['sipp'] = get_generic_config(child)

    return separate_scenarios


def write_scenarios(name, separate_scenarios):
    '''
    Function to write separate scenarios to /opt/output/<scenario_name>/voip_patrol.xml and /opt/output/<scenario_name>/database.xml
    '''

    # Strip the ".XML"
    scenario_name = name.split(".")[0]
    scenario_dir_path = f"/opt/output/{scenario_name}"
    if not os.path.exists(scenario_dir_path):
        os.mkdir(scenario_dir_path)

    vp_scenario_tree = separate_scenarios.get("voip_patrol")
    if vp_scenario_tree:
        vp_scenario_tree.write(f"{scenario_dir_path}/voip_patrol.xml")

    db_scenario_tree = separate_scenarios.get("database")
    if db_scenario_tree:
        db_scenario_tree.write(f"{scenario_dir_path}/database.xml")

    media_scenario_tree = separate_scenarios.get("media_check")
    if media_scenario_tree:
        media_scenario_tree.write(f"{scenario_dir_path}/media_check.xml")

    sipp_scenario_tree = separate_scenarios.get("sipp")
    if sipp_scenario_tree:
        sipp_scenario_tree.write(f"{scenario_dir_path}/sipp.xml")

def get_generic_config(config):
    '''
    Take an media_check config and make new root - <config> for it
    '''
    if config[0].tag != 'actions':
        raise Exception('Tag is not <actions>')

    root = ET.Element('config' , attrib=None, nsmap=None)
    root.append(config[0])

    return ET.ElementTree(root)


def get_vp_config(config):
    '''
    Take an voip_patrol/media_check config and make new root - <config> for it
    Also replace check transport for wss and replace it with tls and add outbound proxy in this case
    '''
    if config[0].tag != 'actions':
        raise Exception('Tag is not <actions>')

    actions = config[0]

    # Relpace wss transport with tls
    for elem in actions:
        if elem.tag == 'action' and elem.attrib.get('transport') == 'wss':
            elem.set('transport', 'tls')
            # Set outbound proxy where it's supported
            if elem.attrib.get('type') in ['call', 'register']:
                proxy_tls_port = os.environ.get('OPENSIPS_TLS_PORT', 6051)
                elem.set('proxy', f"127.0.0.1:{proxy_tls_port}")

    root = ET.Element('config' , attrib=None, nsmap=None)
    root.append(actions)

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
        root = ET.Element('config', attrib=None, nsmap=None)
        root.append(actions)

        return ET.ElementTree(root)

    for action in actions:

        db_name = action.attrib.get('database')
        if not db_name:
            continue

        current_db_config = db_common_config.get(db_name)
        if not current_db_config:
            continue

        current_db_info = ET.SubElement(action, 'info', attrib=None, nsmap=None)
        for k, v in current_db_config.items():
            current_db_info.attrib[k] = v

    root = ET.Element('config', attrib=None, nsmap=None)
    root.append(actions)

    return ET.ElementTree(root)

def process_scenario(name, combined_config, log_level):
    '''
    Here we taking template and making valid voip_patrol and database scenarios.
    '''
    result_xml = scenario_from_template(name, combined_config)
    if result_xml is None:
        return
    
    if log_level >= 1:
        print(f"Processing {name}")

    separate_scenarios = separate_scenario(result_xml, combined_config)
    write_scenarios(name, separate_scenarios)

# Main script starting

# Log level for the console
try:
    log_level = int(os.environ.get("LOG_LEVEL", "1"))
except:
    log_level = 1

try:

    if log_level >= 1:
        print("Starting preparing template(s)...")

    try:
        os.remove("/opt/output/scenarios.done")
    except:
        pass

    with open(r"/opt/input/config.yaml") as config_file:
        if log_level >= 1:
            print("Reading config.yaml...")
        config = yaml.load(config_file, Loader=yaml.FullLoader)

    # Read main config.yaml and prepare python dicts
    global_config = config.get('global')

    if 'domain' not in global_config:
        global_config['domain'] = ''

    if 'transport' not in global_config:
        global_config['transport'] = 'udp'

    if 'srtp' not in global_config:
        global_config['srtp'] = 'none'

    account_config = config.get('accounts')
    account_config_mixed = {}

    if account_config:
        for key in account_config:
            if not isinstance(key, (int, str)):
                continue

            account_config_mixed[key] = account_config[key]
            account_config_mixed[key]['label'] = key

            # Inherit global_config to all accounts
            for k,v in global_config.items():
                account_config_mixed[key][k] = account_config[key].get(k, global_config[k])

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
        process_scenario(single_scenario, combined_config, log_level)
    else:
        for filename in os.listdir('/opt/input'):
            process_scenario(filename, combined_config, log_level)

    pathlib.Path('/opt/output/scenarios.done').touch(mode=777)

except Exception as e:
    print(f"[ERROR]: Error preparing: {e} in {filename}{single_scenario}")

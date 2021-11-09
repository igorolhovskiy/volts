import os
import pathlib
import yaml
from jinja2 import Template


def write_file_from_template(scenario_name, config):
    if not scenario_name.lower().endswith(".xml"):
        return

    with open(r'/opt/input/{}'.format(scenario_name)) as template_file:
            template = Template(template_file.read())

    result_scenario = template.render(c=config["c"], a=config["a"])

    with open(r'/opt/output/{}'.format(scenario_name), 'w') as out_file:
        out_file.write(result_scenario)

try:
    with open(r'/opt/input/config.yaml') as config_file:
        config = yaml.load(config_file, Loader=yaml.FullLoader)

    global_config = config.get('global')

    default_domain = global_config.get('domain') or ''
    default_transport = global_config.get('transport') or 'udp'
    default_srtp = global_config.get('srtp') or 'none'

    account_config = config.get('accounts')
    if account_config:
        account_config_mixed = {}
        for key in account_config:
            if not isinstance(key, (int, str)):
                continue

            account_config_mixed[key] = account_config[key]
            account_config_mixed[key]['label'] = key
            account_config_mixed[key]['domain'] = account_config[key].get('domain') or default_domain
            account_config_mixed[key]['transport'] = account_config[key].get('transport') or default_transport
            account_config_mixed[key]['srtp'] = account_config[key].get('srtp') or default_srtp

            if type(key) is str and key.isnumeric():
                account_config_mixed[int(key)] = account_config_mixed[key]

    single_scenario = os.environ.get("SCENARIO_NAME")

    combined_config = {
        "a": account_config_mixed,
        "c": global_config
    }

    if single_scenario and single_scenario != "":
        single_scenario = single_scenario.split("/")[-1]
        write_file_from_template(single_scenario, combined_config)
    else:
        for filename in os.listdir('/opt/input'):
            write_file_from_template(filename, combined_config)

    pathlib.Path('/opt/output/scenarios.done').touch(mode=777)

except Exception as e:
    print("Error preparing: {}".format(e))

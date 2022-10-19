import os.path
import json
import sys
import xml.etree.ElementTree as ET
from modules.SoXProcess import SoXProcess


def write_report(filename, report):
    report['status'] = "PASS"

    error = report.get("error", "")
    if len(error) > 0:
        report['status'] = "FAIL"
        report['error'] = report['error'].strip('\n')

    report_line = json.dumps(report)
    report_line += "\n"

    filename_path = "/output/{}".format(filename)
    try:
        f_report = open(filename_path, "a")
        f_report.seek(0, 2)
        f_report.write(report_line)
        f_report.close()
    except:
        pass

### SCRIPT START
scenario_name = os.environ.get("SCENARIO")

report_file = os.environ.get("RESULT_FILE", "media_check.jsonl")

scenario_file = '/xml/{}.xml'.format(scenario_name)
if not os.path.exists(scenario_file):
    print("Media check scenario file is absent for {}, skipping...".format(scenario_name))
    sys.exit(0)

report = {}
report['scenario'] = scenario_name
report['error'] = ''

try:
    tree = ET.parse(scenario_file)
    scenario_root = tree.getroot()
except Exception as e:
    report['error'] = "Problem parsing {}".format(e)
    write_report(report_file, report)
    sys.exit(1)

if scenario_root.tag != 'config':
    report['error'] = "Scenario root tag is not <config>, exiting..."
    write_report(report_file, report)
    sys.exit(1)

try:
    if scenario_root[0].tag != 'actions':
        report['error'] = "Scenario missing <actions>, exiting..."
        write_report(report_file, report)
        sys.exit(1)
except:
    report['error'] = "Scenario missing <actions>, exiting..."
    write_report(report_file, report)
    sys.exit(1)

actions = scenario_root[0]

for action in actions:
    if action.tag != 'action':
        print("Tag {} is not supported, skipping ...".format(action.tag))
        continue

    media_type_check = action.attrib.get('type')

    if media_type_check is None:
        print("<type> attribute not found, skipping ...")
        continue

    media_file = action.attrib.get('file')
    if media_file is None:
        print("<file> attribute not found, skipping...")
        continue

    media_type_check = media_type_check.lower()

    if media_type_check not in ('sox'):
        print("Media check {} is not supported, currently supported: sox".format(media_type_check))
        continue

    file_delete_after = action.attrib.get('delete_after', 'true')
    print_debug = action.attrib.get('print_debug', 'no')

    # SoX media processing
    if media_type_check == 'sox':
        print("Start SoX processing over {}".format(media_file))

        sox_filter = action.attrib.get('sox_filter', '')

        if len(sox_filter) == 0:
            print("<sox_filter> for media type <sox> is empty, is it for purpose?")

        try:
            sox_file = SoXProcess(media_file)
            sox_result = sox_file.apply_filter(sox_filter)
            if sox_result is not None:
                raise Exception(sox_result)
        except Exception as e:
            report['error'] += "{}\n".format(e)

        if print_debug.lower() in ('true', 'yes', '1', 'on'):
            sox_file_stats_formatted = json.dumps(sox_file.get_file_stats(), indent=4)

            print("[INFO] SoX data for {}:\n{}".format(media_file, sox_file_stats_formatted))

        if file_delete_after.lower() in ('true', 'yes', '1', 'on'):
            try:
                os.unlink(media_file)
            except Exception as e:
                report['error'] += "{}\n".format(e)

write_report(report_file, report)

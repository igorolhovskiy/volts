# Form XML scenario from XML file provided by prepare
import sys
import os
import json
import subprocess
import random
import time
import socket

import lxml.etree as ET

def write_report(filename, report):
    report['status'] = "PASS"

    error = report.get("error", "")
    if len(error) > 0:
        report['status'] = "FAIL"

    report_line = json.dumps(report)
    report_line += "\n"

    filename_path = f"/output/{filename}"
    try:
        f_report = open(filename_path, "a")
        f_report.seek(0, 2)
        f_report.write(report_line)
        f_report.close()
    except:
        pass

def call_sipp(scenario_path, target, transport, log_level):
    '''
    Here we're calling sipp
    '''
    if not os.path.exists(scenario_path):
        return f"Scenario file <{scenario_path}> is absent...\n"

    tmp_media_port = random.randrange(50000, 60000)
    ip_address = socket.gethostbyname(socket.gethostname())

    cmd = [
        '/usr/bin/timeout',
        '600s',
        '/usr/local/bin/sipp',
        '-sf',
        scenario_path,
        '-m',
        '1',
        '-min_rtp_port',
        str(tmp_media_port),
        '-max_rtp_port',
        str(tmp_media_port + 10),
        '-i',
        ip_address,
        '-trace_err',
        '-error_file',
        'sipp_err.log'
    ]
    if transport == 'tcp':
        cmd.extend(['-t', 't1', target])
    elif transport == 'tls':
        cmd.extend(['-t', 'l1', '-tls_cert', '/etc/ssl/certs/ssl-cert-snakeoil.pem', '-tls_key', '/etc/ssl/private/ssl-cert-snakeoil.key'])
        # Check for port in a case of TLS transport
        if len(target.split(':')) == 1:
            cmd.extend([f"{target}:5061"])

    if log_level > 1:
        sipp_cmd = " ".join(cmd)
        print(f"SIPP command:\n{sipp_cmd}")

    # Run SIPP
    sipp_p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Wait until process terminates (without using p.wait())
    while sipp_p.poll() is None:
        # Process hasn't exited yet, let's wait some
        time.sleep(0.02)

    # Get return code from process
    return_code = sipp_p.returncode
    out, err = sipp_p.communicate()

    if log_level > 0:
        print(f"SIPP exit code:{return_code}")
    if log_level > 1:
        print(f"SIPP out data:\n{out.decode()}")
    if log_level > 2:
        print(f"SIPP err data:\n{err.decode()}")

        if os.path.exists("sipp_err.log"):
            with open("sipp_err.log", 'r') as f:
                print(f.read())

    if return_code == 0:
        return ""

    return f"SIPP exited abnormally: {return_code}\nOut: {out}\nErr: {err}"

### SCRIPT START
scenario_name = os.environ.get("SCENARIO")
report_file = os.environ.get("RESULT_FILE", "sipp.jsonl")
log_level = int(os.environ.get("LOG_LEVEL", "0"))

scenario_file = f"/xml/{scenario_name}.xml"
if not os.path.exists(scenario_file):
    print(f"SIPP scenario file is absent for {scenario_name}, skipping...")
    sys.exit(0)

report = {}
report['scenario'] = scenario_name
report['error'] = ''

try:
    parser = ET.XMLParser(strip_cdata=False, remove_comments=True)

    tree = ET.parse(scenario_file, parser=parser)
    scenario_root = tree.getroot()
except Exception as e:
    report['error'] = f"Problem parsing {e}"
    write_report(report_file, report)
    sys.exit(1)

if scenario_root.tag != 'config':
    report['error'] = "Scenario root tag is not <config>, exiting..."
    write_report(report_file, report)
    sys.exit(1)

try:
    actions = scenario_root[0]
    action = actions[0]
    sipp_scenario = ET.ElementTree(action[0])

    if actions.tag != 'actions' or action.tag != 'action':
        report['error'] = "Scenario missing <actions>/<action>, exiting..."
        write_report(report_file, report)
        sys.exit(1)
except Exception as e:
    report['error'] = f"Scenario missing <actions> ({e}), exiting..."
    write_report(report_file, report)
    sys.exit(1)

target = action.attrib.get('target')
transport = action.attrib.get('transport', 'udp').lower()

if target is None:
    report['error'] = "SIPP target is not specified"
    write_report(report_file, report)
    sys.exit(1)

if transport not in ['tcp', 'udp', 'tls']:
    report['error'] = f"SIPP invalid transport: {transport}"
    write_report(report_file, report)
    sys.exit(1)

if log_level > 1:
    sipp_file = ET.tostring(sipp_scenario).decode()
    print(f"SIPP generated file:\n{sipp_file}")

sipp_scenario_file = '/root/sipp.xml'
try:
    sipp_scenario.write(sipp_scenario_file, xml_declaration=True, encoding="us-ascii")
except Exception as e:
    report['error'] = f"Problem writing {sipp_scenario_file}"
    write_report(report_file, report)
    sys.exit(1)

report['error'] = call_sipp(sipp_scenario_file, target, transport, log_level)
write_report(report_file, report)

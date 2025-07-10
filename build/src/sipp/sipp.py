# Form XML scenario from XML file provided by prepare
import sys
import os
import json
import subprocess
import random
import time
import socket
from pathlib import Path

# Add common utilities to path
sys.path.insert(0, '/root/common')
from logger import setup_logger, get_log_level, ErrorReporter

import lxml.etree as ET

def write_report(filename, report, logger=None):
    """
    Write report to file with proper error handling.
    
    Args:
        filename: Output filename
        report: Report dictionary
        logger: Optional logger instance
    """
    report['status'] = "PASS"

    error = report.get("error", "")
    if len(error) > 0:
        report['status'] = "FAIL"

    report_line = json.dumps(report)
    report_line += "\n"

    filename_path = f"/output/{filename}"
    try:
        with open(filename_path, "a") as f_report:
            f_report.seek(0, 2)
            f_report.write(report_line)
    except (IOError, OSError, PermissionError) as e:
        error_msg = f"Failed to write report to {filename_path}: {e}"
        if logger:
            logger.error(error_msg)
        else:
            print(f"ERROR: {error_msg}")
    except Exception as e:
        error_msg = f"Unexpected error writing report to {filename_path}: {e}"
        if logger:
            logger.error(error_msg)
        else:
            print(f"ERROR: {error_msg}")

def call_sipp(scenario_path, target, transport, log_level, max_calls, call_rate, max_ccalls, total_timeout, socket_mode, logger=None):
    '''
    Here we're calling sipp with proper error handling
    '''
    if not os.path.exists(scenario_path):
        return f"Scenario file <{scenario_path}> is absent...\n"

    tmp_media_port = random.randrange(50000, 60000)
    
    try:
        ip_address = socket.gethostbyname(socket.gethostname())
    except socket.gaierror as e:
        error_msg = f"Failed to resolve hostname: {e}"
        if logger:
            logger.error(error_msg)
        return f"Network error: {error_msg}\n"
    except Exception as e:
        error_msg = f"Unexpected error getting IP address: {e}"
        if logger:
            logger.error(error_msg)
        return f"Network error: {error_msg}\n"

    cmd = [
        '/usr/bin/timeout',
        f"{total_timeout}s",
        '/usr/local/bin/sipp',
        '-sf',
        scenario_path,
        '-m',
        str(max_calls),
        '-r',
        str(call_rate),
        '-l',
        str(max_ccalls),
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

    socket_extender = "1"
    if socket_mode.lower() == "multi":
        socket_extender = "n"

    if transport == 'tcp':
        cmd.extend(['-t', f"t{socket_extender}", target])
    elif transport == 'tls':
        cmd.extend(['-t', f"l{socket_extender}", '-tls_cert', '/etc/ssl/certs/ssl-cert-snakeoil.pem', '-tls_key', '/etc/ssl/private/ssl-cert-snakeoil.key'])
        # Check for port in a case of TLS transport
        if ':' not in target:
            cmd.extend([f"{target}:5061"])
    else:
        # UDP
        cmd.extend(['-t', f"u{socket_extender}", target])

    if log_level > 1:
        sipp_cmd = " ".join(cmd)
        if logger:
            logger.info(f"SIPP command:\n{sipp_cmd}")
        else:
            print(f"SIPP command:\n{sipp_cmd}")

    # Run SIPP
    try:
        sipp_p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Wait until process terminates (without using p.wait())
        while sipp_p.poll() is None:
            # Process hasn't exited yet, let's wait some
            time.sleep(0.02)

        # Get return code from process
        return_code = sipp_p.returncode
        out, err = sipp_p.communicate()

    except FileNotFoundError as e:
        error_msg = f"SIPP executable not found: {e}"
        if logger:
            logger.error(error_msg)
        return f"Execution error: {error_msg}\n"
    except PermissionError as e:
        error_msg = f"Permission denied executing SIPP: {e}"
        if logger:
            logger.error(error_msg)
        return f"Permission error: {error_msg}\n"
    except subprocess.SubprocessError as e:
        error_msg = f"SIPP process error: {e}"
        if logger:
            logger.error(error_msg)
        return f"Process error: {error_msg}\n"
    except Exception as e:
        error_msg = f"Unexpected error running SIPP: {e}"
        if logger:
            logger.error(error_msg)
        return f"Execution error: {error_msg}\n"

    if log_level > 0:
        log_msg = f"SIPP exit code:{return_code}"
        if logger:
            logger.info(log_msg)
        else:
            print(log_msg)
    
    if log_level > 1:
        try:
            out_str = out.decode('utf-8', errors='replace')
            if logger:
                logger.info(f"SIPP out data:\n{out_str}")
            else:
                print(f"SIPP out data:\n{out_str}")
        except Exception as e:
            if logger:
                logger.warning(f"Failed to decode SIPP output: {e}")
                
    if log_level > 2:
        try:
            err_str = err.decode('utf-8', errors='replace')
            if logger:
                logger.info(f"SIPP err data:\n{err_str}")
            else:
                print(f"SIPP err data:\n{err_str}")
        except Exception as e:
            if logger:
                logger.warning(f"Failed to decode SIPP error output: {e}")

        if os.path.exists("sipp_err.log"):
            try:
                with open("sipp_err.log", 'r') as f:
                    log_content = f.read()
                    if logger:
                        logger.info(f"SIPP error log:\n{log_content}")
                    else:
                        print(log_content)
            except (IOError, OSError) as e:
                if logger:
                    logger.warning(f"Failed to read SIPP error log: {e}")

    if return_code == 0:
        return ""

    try:
        out_str = out.decode('utf-8', errors='replace')
        err_str = err.decode('utf-8', errors='replace')
    except Exception:
        out_str = str(out)
        err_str = str(err)

    return f"SIPP exited abnormally: {return_code}\nOut: {out_str}\nErr: {err_str}"

### SCRIPT START
scenario_name = os.environ.get("SCENARIO")
report_file = os.environ.get("RESULT_FILE", "sipp.jsonl")

# Initialize logging
log_level = get_log_level()
logger = setup_logger(__name__, log_level)
error_reporter = ErrorReporter(logger)

logger.info(f"Starting SIPP for scenario: {scenario_name}")
logger.debug(f"Report file: {report_file}, Log level: {log_level}")

scenario_file = f"/xml/{scenario_name}.xml"
if not os.path.exists(scenario_file):
    logger.info(f"SIPP scenario file is absent for {scenario_name}, skipping...")
    sys.exit(0)

report = {}
report['scenario'] = scenario_name
report['error'] = ''

try:
    parser = ET.XMLParser(strip_cdata=False, remove_comments=True)
    tree = ET.parse(scenario_file, parser=parser)
    scenario_root = tree.getroot()
    logger.debug(f"Successfully parsed XML file: {scenario_file}")
except ET.XMLSyntaxError as e:
    error_msg = f"XML syntax error in {scenario_file}: {e}"
    error_reporter.add_error(error_msg, e)
    report['error'] = error_msg
    write_report(report_file, report, logger)
    sys.exit(1)
except (FileNotFoundError, IOError, OSError) as e:
    error_msg = f"File access error for {scenario_file}: {e}"
    error_reporter.add_error(error_msg, e)
    report['error'] = error_msg
    write_report(report_file, report, logger)
    sys.exit(1)
except Exception as e:
    error_msg = f"Unexpected error parsing {scenario_file}: {e}"
    error_reporter.add_error(error_msg, e)
    report['error'] = error_msg
    write_report(report_file, report, logger)
    sys.exit(1)

if scenario_root.tag != 'config':
    error_msg = "Scenario root tag is not <config>, exiting..."
    error_reporter.add_error(error_msg)
    report['error'] = error_msg
    write_report(report_file, report, logger)
    sys.exit(1)

try:
    if len(scenario_root) == 0:
        raise IndexError("No child elements found")
    
    actions = scenario_root[0]
    if actions.tag != 'actions':
        raise ValueError("First child is not <actions>")
    
    if len(actions) == 0:
        raise IndexError("No action elements found")
    
    action = actions[0]
    if action.tag != 'action':
        raise ValueError("First action child is not <action>")
    
    if len(action) == 0:
        raise IndexError("No scenario elements found in action")
    
    sipp_scenario = ET.ElementTree(action[0])
    
except (IndexError, ValueError) as e:
    error_msg = f"Scenario structure error: {e}"
    error_reporter.add_error(error_msg, e)
    report['error'] = error_msg
    write_report(report_file, report, logger)
    sys.exit(1)
except Exception as e:
    error_msg = f"Unexpected error accessing scenario structure: {e}"
    error_reporter.add_error(error_msg, e)
    report['error'] = error_msg
    write_report(report_file, report, logger)
    sys.exit(1)

target = action.attrib.get('target')
transport = action.attrib.get('transport', 'udp').lower()
call_rate = action.attrib.get('call_rate', '10')
max_calls = action.attrib.get('max_calls', '1')
max_ccalls = action.attrib.get('max_concurrent_calls', '10')
total_timeout = action.attrib.get('total_timeout', '600')
socket_mode = action.attrib.get('socket_mode', 'single')

if target is None:
    error_msg = "SIPP target is not specified"
    error_reporter.add_error(error_msg)
    report['error'] = error_msg
    write_report(report_file, report, logger)
    sys.exit(1)

if transport not in ['tcp', 'udp', 'tls']:
    error_msg = f"SIPP invalid transport: {transport}"
    error_reporter.add_error(error_msg)
    report['error'] = error_msg
    write_report(report_file, report, logger)
    sys.exit(1)

if log_level > 1:
    try:
        sipp_file = ET.tostring(sipp_scenario).decode()
        logger.info(f"SIPP generated file:\n{sipp_file}")
    except Exception as e:
        logger.warning(f"Failed to decode SIPP scenario XML: {e}")

sipp_scenario_file = '/root/sipp.xml'
try:
    sipp_scenario.write(sipp_scenario_file, xml_declaration=True, encoding="us-ascii")
    logger.debug(f"Successfully wrote SIPP scenario file: {sipp_scenario_file}")
except (IOError, OSError, PermissionError) as e:
    error_msg = f"Failed to write SIPP scenario file {sipp_scenario_file}: {e}"
    error_reporter.add_error(error_msg, e)
    report['error'] = error_msg
    write_report(report_file, report, logger)
    sys.exit(1)
except Exception as e:
    error_msg = f"Unexpected error writing SIPP scenario file {sipp_scenario_file}: {e}"
    error_reporter.add_error(error_msg, e)
    report['error'] = error_msg
    write_report(report_file, report, logger)
    sys.exit(1)

logger.info(f"Calling SIPP with target: {target}, transport: {transport}")
report['error'] = call_sipp(
                        scenario_path=sipp_scenario_file,
                        target=target,
                        transport=transport,
                        log_level=log_level,
                        max_calls=max_calls,
                        call_rate=call_rate,
                        max_ccalls=max_calls,
                        total_timeout=total_timeout,
                        socket_mode=socket_mode,
                        logger=logger
                    )

logger.info(f"SIPP completed for scenario: {scenario_name}")
write_report(report_file, report, logger)

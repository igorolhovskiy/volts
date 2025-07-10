import os
import os.path
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Add common utilities to path
sys.path.insert(0, '/root/common')

from logger import setup_logger, get_log_level, ErrorReporter
from modules.SoXProcess import SoXProcess


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
        report['error'] = report['error'].strip('\n')

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


# SCRIPT START
scenario_name = os.environ.get("SCENARIO")
report_file = os.environ.get("RESULT_FILE", "media_check.jsonl")

# Initialize logging
log_level = get_log_level()
logger = setup_logger(__name__, log_level)
error_reporter = ErrorReporter(logger)

logger.info(f"Starting media check for scenario: {scenario_name}")
logger.debug(f"Report file: {report_file}, Log level: {log_level}")

scenario_file = f"/xml/{scenario_name}.xml"
if not os.path.exists(scenario_file):
    logger.info(f"Media check scenario file is absent for {scenario_name}, skipping...")
    sys.exit(0)

report = {}
report['scenario'] = scenario_name
report['error'] = ''

try:
    tree = ET.parse(scenario_file)
    scenario_root = tree.getroot()
    logger.debug(f"Successfully parsed XML file: {scenario_file}")
except ET.ParseError as e:
    error_msg = f"XML parse error in {scenario_file}: {e}"
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
    if len(scenario_root) == 0 or scenario_root[0].tag != 'actions':
        error_msg = "Scenario missing <actions>, exiting..."
        error_reporter.add_error(error_msg)
        report['error'] = error_msg
        write_report(report_file, report, logger)
        sys.exit(1)
except (IndexError, AttributeError) as e:
    error_msg = f"Scenario structure error: {e}"
    error_reporter.add_error(error_msg, e)
    report['error'] = error_msg
    write_report(report_file, report, logger)
    sys.exit(1)

actions = scenario_root[0]

for action in actions:
    if action.tag != 'action':
        logger.warning(f"Tag {action.tag} is not supported, skipping...")
        continue

    media_type_check = action.attrib.get('type')

    if media_type_check is None:
        logger.warning("<type> attribute not found, skipping...")
        continue

    media_file = action.attrib.get('file')
    if media_file is None:
        logger.warning("<file> attribute not found, skipping...")
        continue

    media_type_check = media_type_check.lower()

    if media_type_check not in ('sox'):
        logger.warning(f"Media check {media_type_check} is not supported, currently supported: sox")
        continue

    file_delete_after = action.attrib.get('delete_after', 'keep_failed')
    print_debug = action.attrib.get('print_debug', 'no')

    # SoX media processing
    if media_type_check == 'sox':
        logger.info(f"Start SoX processing over {media_file}")

        sox_filter = action.attrib.get('sox_filter', '')

        if len(sox_filter) == 0:
            logger.warning("<sox_filter> for media type <sox> is empty, is it for purpose?")

        try:
            sox_file = SoXProcess(media_file)
            sox_file_stats_formatted = json.dumps(sox_file.get_file_stats(), indent=4)

            if print_debug.lower() in ('true', 'yes', '1', 'on'):
                print(f"SoX data for {media_file}:\n{sox_file_stats_formatted}")
            elif log_level >= 3:
                logger.debug(f"SoX data for {media_file}:\n{sox_file_stats_formatted}")

            sox_result = sox_file.apply_filter(sox_filter)
            if sox_result is not None:
                error_msg = f"SoX filter failed: {sox_result}"
                error_reporter.add_error(error_msg)
                report['error'] += f"{error_msg}\n"

        except FileNotFoundError as e:
            error_msg = f"Media file not found: {media_file}"
            error_reporter.add_error(error_msg, e)
            report['error'] += f"{error_msg}\n"
        except PermissionError as e:
            error_msg = f"Permission denied accessing media file: {media_file}"
            error_reporter.add_error(error_msg, e)
            report['error'] += f"{error_msg}\n"
        except Exception as e:
            error_msg = f"SoX processing failed for {media_file}: {e}"
            error_reporter.add_error(error_msg, e)
            report['error'] += f"{error_msg}\n"

        # We're deleting a file only in a case if it asked explicitly
        # or there were no error
        if (file_delete_after.lower() in ('true', 'yes', '1', 'on')
            or (file_delete_after.lower() == 'keep_failed'
                and len(report['error']) == 0)):
            try:
                os.unlink(media_file)
                logger.debug(f"Deleted media file: {media_file}")
            except FileNotFoundError:
                logger.debug(f"Media file already deleted: {media_file}")
            except PermissionError as e:
                error_msg = f"Permission denied deleting media file: {media_file}"
                error_reporter.add_error(error_msg, e)
                report['error'] += f"{error_msg}\n"
            except Exception as e:
                error_msg = f"Error deleting media file {media_file}: {e}"
                error_reporter.add_error(error_msg, e)
                report['error'] += f"{error_msg}\n"

logger.info(f"Media check completed for scenario: {scenario_name}")
write_report(report_file, report, logger)

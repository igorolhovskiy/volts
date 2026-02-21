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
from modules.Chromaprint import Chromaprint


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


files_to_delete = set()
files_to_keep = set()

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

    media_file_st = media_file

    media_type_check = media_type_check.lower()
    error_msg = ""

    if media_type_check not in ('sox', 'sox_st', 'fpcalc'):
        logger.warning(f"Media check {media_type_check} is not supported, currently supported: sox, sox_st, fpcalc")
        continue

    file_delete_after = action.attrib.get('delete_after', 'keep_failed').lower()
    print_debug = action.attrib.get('print_debug', 'no').lower()

    # SoX media processing
    if media_type_check in ('sox', 'sox_st'):

        sox_filter = action.attrib.get('sox_filter', '')
        silence_trim = True if media_type_check == 'sox_st' else False
        tool_name = "SoX Silece Trim" if media_type_check == 'sox_st' else "SoX"

        logger.info(f"Start {tool_name} processing over {media_file}")

        if len(sox_filter) == 0:
            logger.warning(f"<sox_filter> for media type <{media_type_check}> is empty, is it for purpose?")

        try:
            sox_file = SoXProcess(media_file, silence_trim)
            sox_file_stats_formatted = json.dumps(sox_file.get_file_stats(), indent=4)

            if print_debug in ('true', 'yes', '1', 'on'):
                print(f"{tool_name} data for {media_file}:\n{sox_file_stats_formatted}")
            elif log_level >= 3:
                logger.debug(f"{tool_name} data for {media_file}:\n{sox_file_stats_formatted}")

            sox_result = sox_file.apply_filter(sox_filter)
            if sox_result is not None:
                error_msg = f"{tool_name} filter failed for <{media_file}>: {sox_result}"
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
            error_msg = f"{tool_name} processing failed for {media_file}: {e}"
            error_reporter.add_error(error_msg, e)
            report['error'] += f"{error_msg}\n"

        # We're deleting a file only in a case if it asked explicitly
        # or there were no error
        if (file_delete_after in ('true', 'yes', '1', 'on')
            or (file_delete_after == 'keep_failed' and error_msg == "")):
            files_to_delete.add(media_file)
        else:
            files_to_keep.add(media_file)

    # Testing fpcalc
    if media_type_check == 'fpcalc':
        fpcalc_fp = action.attrib.get('fingerprint', '')
        fpcalc_fp = fpcalc_fp.split(",")

        fpcalc_dmax = 0
        fpcalc_dmin = 0

        fpcalc_offset = int(action.attrib.get('max_offset', 50))
        fpcalc_likeness = float(action.attrib.get('likeness', 0.9))
        fpcalc_duration = action.attrib.get('length')
        if fpcalc_duration is not None:
            if "-" in fpcalc_duration:
                fpcalc_duration = fpcalc_duration.split('-')
                if len(fpcalc_duration) == 2:
                    fpcalc_dmax = float(fpcalc_duration[1])
                    fpcalc_dmin = float(fpcalc_duration[0])
            else:
                fpcalc_dmax = float(fpcalc_duration)
                fpcalc_dmin = fpcalc_dmax

        logger.info(f"Start fpcalc processing over {media_file}")

        if len(fpcalc_fp) == 0:
            logger.warning(f"<fingerprint> for media type <fpcalc> is empty, is it for purpose?")

        try:

            fpcalc_file = Chromaprint(media_file)
            fpcalc_file._set_fpcalc_fingerprint()
            likeness, best_offset = fpcalc_file.get_likeness(fpcalc_fp)
            duration = fpcalc_file.get_duration()

            if print_debug in ('true', 'yes', '1', 'on'):
                print(f"fpcalc data for {media_file}:\n{fpcalc_file.fingerprint}\nLength: {duration} Likeness:{likeness} Best offset:{best_offset}")
            elif log_level >= 3:
                logger.debug(f"fpcalc data for {media_file}:\n{fpcalc_file.fingerprint}\nLength: {duration} Likeness:{likeness} Best offset:{best_offset}")

            if fpcalc_likeness > float(likeness):
                error_msg = f"fpcalc likeness failed for <{media_file}>: {fpcalc_likeness} > {likeness}"
                error_reporter.add_error(error_msg)
                report['error'] += f"{error_msg}\n"

            # We have a duration
            if fpcalc_dmax + fpcalc_dmin != 0:
                duration = float(duration)
                if duration > fpcalc_dmax or duration < fpcalc_dmin:
                    error_msg = f"fpcalc length failed for <{media_file}>: {fpcalc_dmin} > {duration} > {fpcalc_dmax}"
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
            error_msg = f"fpcalc processing failed for {media_file}: {e}"
            error_reporter.add_error(error_msg, e)
            report['error'] += f"{error_msg}\n"

        # We're deleting a file only in a case if it asked explicitly
        # or there were no error
        if (file_delete_after in ('true', 'yes', '1', 'on')
            or (file_delete_after == 'keep_failed' and error_msg == "")):
            files_to_delete.add(media_file)
        else:
            files_to_keep.add(media_file)

logger.debug(f"List of media to delete: {files_to_delete}")
logger.debug(f"List of media to keep: {files_to_keep}")

files_to_delete = files_to_delete - files_to_keep
for file_to_delete in files_to_delete:
    if os.path.exists(file_to_delete):
        try:
            os.unlink(file_to_delete)
            logger.debug(f"Deleted media file: {file_to_delete}")
        except FileNotFoundError:
            logger.debug(f"File already deleted???: {file_to_delete}")
        except PermissionError as e:
            error_msg = f"Permission denied deleting media file: {file_to_delete}"
            error_reporter.add_error(error_msg, e)
            report['error'] += f"{error_msg}\n"
        except Exception as e:
            error_msg = f"Error deleting media file {file_to_delete}: {e}"
            error_reporter.add_error(error_msg, e)
            report['error'] += f"{error_msg}\n"
    else:
        logger.debug(f"File not found: {file_to_delete}")

logger.info(f"Media check completed for scenario: {scenario_name}")
write_report(report_file, report, logger)

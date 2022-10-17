import json
import os
from prettytable import PrettyTable

def process_jsonl_file(file):
    """
    Function to process output of voip_patrol, which is JSONL (https://jsonlines.org/) file
    """
    processed_data = list()
    error = None

    for line in file:
        if len(line) <= 1:
            continue
        try:
            processed_data.append(json.loads(line))
        except ValueError as e:
            error = "Line {} is not a JSON: {}".format(line, e)

    return error, processed_data

def get_tests_list():
    """
    Function to get all tests lists from all tests directory.
    List of tests = list of directories
    """
    test_list = list()
    for scenario_name in os.listdir('/opt/scenarios'):
        scenario_folder_path = os.path.join('/opt/scenarios', scenario_name)
        if os.path.isdir(scenario_folder_path):
            test_list.append(_normalize_test_name(scenario_name))

    return test_list

def _normalize_test_name(name):
    """
    Function to transform "/xml/<test_name>.xml" -> "<test_name>"
    """
    normalized_name = name.split("/")[-1]

    if normalized_name == 'voip_patrol.xml':
        normalized_name = name.split("/")[-2]

    if normalized_name.endswith('.xml'):
        return normalized_name[:-4]

    return normalized_name

def build_test_results(vp_report_data, d_report_data, m_report_data):
    """
    Function to process line-by-line data from *voip_patrol* and *database* JSONL results file
    to a dict with a structure
    "scenario_name": {
        "status": ...
        "start_time": ...
        "end_time": ...
        "tests": {
            ...
        }
        "d_status": ...
        "d_error": {
            "stage": ...
            "text": ...
        }
        "m_status": ...
        "m_error": {

        }
    }
    """
    test_results = {}
    current_test = "orphaned"

    for test_entity in vp_report_data:

        # Scenario process start
        # We got start or end of test
        if test_entity.get("scenario"):
            previous_test = current_test

            current_test_scenario_info = test_entity.get("scenario")

            current_test = current_test_scenario_info.get("name", "orphaned")
            current_test = _normalize_test_name(current_test)

            if current_test_scenario_info.get("state") == "start":

                if current_test not in test_results:
                    test_results[current_test] = {}
                    test_results[current_test]["start_time"] = current_test_scenario_info.get("time")
                    continue

                test_results[current_test]["status"] = "FAIL"
                test_results[current_test]["status_text"] = "Multiple starts"
                continue

            if current_test_scenario_info.get("state") == "end":

                if previous_test != current_test:
                    if current_test not in test_results:
                        test_results[current_test] = {}
                    if previous_test not in test_results:
                        test_results[previous_test] = {}

                    test_results[current_test]["status"] = "FAIL"
                    test_results[current_test]["status_text"] = "Start/End are not aligned"

                    test_results[previous_test]["status"] = "FAIL"
                    test_results[previous_test]["status"] = "Start/End are not aligned"

                    current_test = "orphaned"
                    continue

                if current_test not in test_results:
                    test_results[current_test] = {}
                    test_results[current_test]["status"] = "FAIL"
                    test_results[current_test]["status_text"] = "Bug 1 in the report script, please fix"

                    current_test = "orphaned"
                    continue

                scenario_total_tasks = current_test_scenario_info.get("total tasks", "NA")
                scenario_completed_tasks = current_test_scenario_info.get("completed tasks", "NA")

                test_results[current_test]["end_time"] = current_test_scenario_info.get("time")
                test_results[current_test]["status"] = current_test_scenario_info.get("result", "FAIL")
                test_results[current_test]["counter"] = "{}/{}".format(scenario_completed_tasks, scenario_total_tasks)

                # Status PASS at this moment means only that all tests are completed
                if test_results[current_test]["status"] == "FAIL":
                    test_results[current_test]["status_text"] = "Scenario failed ({} of {} tasks done)".format(scenario_completed_tasks, scenario_total_tasks)

                    current_test = "orphaned"
                    continue

                if test_results[current_test].get("tests"):
                    for test_result_line in test_results[current_test]["tests"].values():
                        test_failed_count = 0
                        if test_result_line.get("result") == "FAIL":
                            test_failed_count += 1
                            test_results[current_test]["status"] = "FAIL"
                            test_results[current_test]["status_text"] = "{} tests has failed".format(test_failed_count)

                if test_results[current_test]["status"] != "FAIL":
                    test_results[current_test]["status"] = "PASS"
                    test_results[current_test]["status_text"] = "Scenario passed"

                current_test = "orphaned"
                continue

            # Scenario state not end nor start. It's a bug
            if current_test not in test_results:
                test_results[current_test] = {}

            test_results[current_test]["status"] = "FAIL"
            test_results[current_test]["status_text"] = "Problem with scenario, unknown state"

            current_test = "orphaned"
            continue
        # Scenario process end

        if len(test_entity) != 1:
            if current_test not in test_results:
                test_results[current_test] = {}

            test_results[current_test]["status"] = "FAIL"
            test_results[current_test]["status_text"] = "Problem with the test info"
            continue

        test_number = next(iter(test_entity)) # Get first and only key in test_entity

        if not test_results[current_test].get("tests"):
            test_results[current_test]["tests"] = {}

        test_results[current_test]["tests"][test_number] = test_entity[test_number]

    # Add FAIL if we have tests without end's
    for current_test, test_result_info in test_results.items():
        if not test_result_info.get("status"):
            test_results[current_test]["status"] = "FAIL"
            test_results[current_test]["status_text"] = "End action missing"
            continue
        if not test_result_info.get("end_time"):
            test_results[current_test]["status"] = "FAIL"
            test_results[current_test]["status_text"] = "End time missing"

        test_results[current_test]["vp_status"] = test_results[current_test]["status"]

    # Enrich results with DB info
    for test_entity in d_report_data:
        if not test_entity.get("scenario"):
            continue

        current_test = test_entity.get("scenario")
        if current_test not in test_results:
            continue

        current_test_d_status = test_entity.get("status", "FAIL")

        current_test_d_existing_status = test_results[current_test].get("d_status")
        if current_test_d_status == "PASS" and current_test_d_existing_status == "PASS":
            continue

        if current_test_d_status != "PASS":
            test_results[current_test]["d_status"] = "FAIL"
            if "d_error" not in test_results[current_test]:
                test_results[current_test]["d_error"] = {}
                test_results[current_test]["d_error"]["stage"] = ""
                test_results[current_test]["d_error"]["text"] = ""

            test_results[current_test]["d_error"]["stage"] += "{} ".format(test_entity.get("stage", "err"))
            test_results[current_test]["d_error"]["text"] += "{} ".format(test_entity.get("error", "err"))
            continue

        if not current_test_d_existing_status:
            test_results[current_test]["d_status"] = "PASS"

        if test_results[current_test].get("d_status") != "PASS":
            test_results[current_test]["status"] = "FAIL"
            test_results[current_test]['status_text'] += " Database failed"

    # Enrich results with media check info
    for test_entity in m_report_data:
        if not test_entity.get("scenario"):
            continue

        current_test = test_entity.get("scenario")
        if current_test not in test_results:
            continue

        current_test_m_status = test_entity.get("status", "FAIL")

        current_test_m_existing_status = test_results[current_test].get("m_status")
        if current_test_m_status == "PASS" and current_test_m_existing_status == "PASS":
            continue

        if current_test_m_status != "PASS":
            test_results[current_test]["m_status"] = "FAIL"
            if "m_error" not in test_results[current_test]:
                test_results[current_test]["m_error"] = {}

            m_error_index = len(test_results[current_test]["m_error"]) + 1
            test_results[current_test]["m_error"].update({m_error_index :test_entity.get("error")})
            continue

        if not current_test_m_existing_status:
            test_results[current_test]["m_status"] = "PASS"

        if test_results[current_test].get("m_status") != "PASS":
            test_results[current_test]["status"] = "FAIL"
            test_results[current_test]['status_text'] += " Media failed"

    return test_results


def align_test_results_with_test_list(test_results, test_list):
    '''
    Make sure report have all tests results, that was in initial test list
    '''
    print("Test list: {}".format(test_list))
    for actual_test in test_list:
        if actual_test in test_results:
            continue

        test_results[actual_test] = {}
        test_results[actual_test]["status"] = "FAIL"
        test_results[actual_test]["status_text"] = "Scenario is not present in the results"

    for actual_test in test_results:
        if actual_test in test_list:
            continue

        test_results[actual_test]["status"] = "FAIL"
        test_results[actual_test]["status_text"] = "Scenario is not present in the scenario list"


def filter_results_default(test_results):
    '''
    Find all failed tests
    '''

    printed_results = {}
    errors = list()


    for scenario_name, scenario_details in test_results.items():
        print("Processing {}".format(scenario_name))
        if scenario_details.get("status") == "PASS":
            continue

        printed_results[scenario_name] = {}
        if scenario_details.get("vp_status", "PASS") != "PASS":
            printed_results[scenario_name]["vp_status"] = scenario_details.get("vp_status")
            printed_results[scenario_name]["status_text"] = scenario_details.get("status_text")
            printed_results[scenario_name]["start_time"] = scenario_details.get("start_time")
            printed_results[scenario_name]["end_time"] = scenario_details.get("end_time")
            printed_results[scenario_name]["task_counter"] = scenario_details.get("counter")

        if scenario_details.get("d_status", "PASS") != "PASS":
            printed_results[scenario_name]["d_status"] = scenario_details.get("d_status")
            printed_results[scenario_name]["d_error"] = scenario_details.get("d_error", "")

        if scenario_details.get("m_status", "PASS") != "PASS":
            printed_results[scenario_name]["m_status"] = scenario_details.get("m_status")
            printed_results[scenario_name]["m_error"] = scenario_details.get("m_error", "")

        errors.append(scenario_name)

        failed_tests = {}
        if scenario_details.get("tests"):
            for test_name, test_details in scenario_details["tests"].items():
                if test_details.get("result") == "PASS":
                    continue
                failed_tests[test_name] = test_details

        if len(failed_tests) > 1:
            printed_results[scenario_name]["failed_tests"] = failed_tests

    status = None
    if len(errors) > 0:
        status = errors

    return status, printed_results

def print_table(print_results):
    tbl = PrettyTable()

    tbl.field_names = ["Scenario", "VoIP Patrol", "Database", "Media", "Status" ,"Text"]

    for scenario_name, scenario_details in print_results.items():
        vp_status_text = scenario_details.get("vp_status", "N/A")
        db_status_text = scenario_details.get("d_status", "N/A")
        m_status_text = scenario_details.get("m_status", "N/A")

        # Getting overall status:
        combined_status = scenario_details.get("status", "N/A")

        tbl.add_row([scenario_name, vp_status_text, db_status_text, m_status_text, combined_status, scenario_details.get("status_text")])

        if not (type(scenario_details.get("tests")) is dict):
            continue

        for test_data in scenario_details.get("tests").values():
            tbl.add_row(["", test_data.get("label"), "", "", test_data.get("result"), test_data.get("result_text")])

    tbl.align = "r"
    print(tbl)

def print_results_json_full(test_results):
    failed_scenarios, printed_results = filter_results_default(test_results)

    print(json.dumps(printed_results, sort_keys=True, indent=4))

    if failed_scenarios is not None:
        print("Scenarios {} are failed!".format(failed_scenarios))
        return

    print("All scenarios are OK!")


def print_results_table_default(test_results):

    failed_scenarios, printed_results = filter_results_default(test_results)

    if failed_scenarios is not None:
        print_table(printed_results)
        print("Scenarios {} are failed!".format(failed_scenarios))
        return

    print("All scenarios are OK!")

def print_results_json_default(test_results):

    error, printed_results = filter_results_default(test_results)

    if error is not None:
        print(json.dumps(printed_results, sort_keys=True, indent=4))
        print("Scenarios {} are failed!".format(error))
        return

    print("All scenarios are OK!")

def print_results_table_full(test_results):
    failed_scenarios, _ = filter_results_default(test_results)

    print_table(test_results)

    if failed_scenarios is not None:
        print("Scenarios {} are failed!".format(failed_scenarios))
        return

    print("All scenarios are OK!")


# Main program starts
try:
    vp_report_file_name = os.environ.get("VP_RESULT_FILE", "result.jsonl")
    vp_report_file_path = r'/opt/report/' + vp_report_file_name

    with open(vp_report_file_path) as report_file:
        process_error, vp_report_data = process_jsonl_file(report_file)
        if process_error:
            raise Exception("Error processing voip_patrol report file: {}".format(process_error))

    d_report_file_name = os.environ.get("D_RESULT_FILE", "database.jsonl")
    d_report_file_path = r'/opt/report/' + d_report_file_name
    d_report_data = {}

    if os.path.exists(d_report_file_path):
        with open(d_report_file_path) as report_file:
            process_error, d_report_data = process_jsonl_file(report_file)
            if process_error:
                raise Exception("Error processing database report file: {}".format(process_error))

    m_report_file_name = os.environ.get("M_RESULT_FILE", "media_check.jsonl")
    m_report_file_path = r'/opt/report/' + m_report_file_name
    m_report_data = {}

    if os.path.exists(m_report_file_path):
        with open(m_report_file_path) as report_file:
            process_error, m_report_data = process_jsonl_file(report_file)
            if process_error:
                raise Exception("Error processing media report file: {}".format(process_error))

    tests_list = get_tests_list()
    test_results = build_test_results(vp_report_data, d_report_data, m_report_data)

    align_test_results_with_test_list(test_results, tests_list)

    print_style = os.environ.get("REPORT_TYPE", "json")
    print_style = print_style.lower()
    if print_style == "json_full":
        print_results_json_full(test_results)
    elif print_style == "table_full":
        print_results_table_full(test_results)
    elif print_style.startswith("table"):
        print_results_table_default(test_results)
    else:
        print_results_json_default(test_results)

except Exception as e:
    print("Error processing report: {}".format(e))

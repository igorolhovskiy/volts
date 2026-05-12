# Script to read XML scenario for database
# and preform actions on them. Multiple databases/tables are supported within 1 scenario
#
# Example of processed XML insering data in subsriber table
#
# <config>
#     <actions>
#         <action database="sippproxydb" stage="pre">
#             <table cleanup_after_test="true" name="subscriber" type="insert">
#                 <field name="username" value="11111" />
#                 <field name="domain" value="mypbx.com" />
#                 <field name="ha1" value="b509095666231146d2650fe1cc1265ec" />
#                 <field name="password" value="dummy_data_here" />
#             </table>
#             <info base="sipproxy"
#                 host="my_sipproxy.host"
#                 password="superSecretDBPassword"
#                 type="mysql"
#                 user="sipproxyrw" />
#         </action>
#     </actions>
# </config>
#
# on stage "pre"
# USE sipproxy;
# INSERT INTO subscriber (username, domain, ha1, password) VALUES ("11111", "mypbx.com", "b509095666231146d2650fe1cc1265ec", "dummy_data_here");
#
# on stage "post"
# USE sipproxy;
# DELETE FROM subscriber WHERE username = "11111" AND domain = "mypbx.com" AND ha1 = "b509095666231146d2650fe1cc1265ec" AND password = "dummy_data_here";
#
# That simple

import xml.etree.ElementTree as ET
import sys
import os
import json
import re
from datetime import datetime as _dt
from pathlib import Path

# Add common utilities to path
sys.path.insert(0, '/root/common')
from logger import setup_logger, get_log_level, ErrorReporter


def get_db_connection(db_options):
    '''
    Get database handler based on type
    '''
    if db_options.get('type') == 'mysql':
        import pymysql
        db_handler = pymysql

    elif db_options.get('type') == 'pgsql':
        import psycopg2
        db_handler = psycopg2
    else:
        return None

    db_connect_options = {
        'user':            db_options['user'],
        'password':        db_options['password'],
        'host':            db_options['host'],
        'port':            int(db_options['port']),
        'database':        db_options['db'],
        'connect_timeout': 5,
    }
    if db_options.get('type') == 'mysql':
        db_connect_options['read_timeout'] = 10
        db_connect_options['write_timeout'] = 10

    return db_handler.connect(**db_connect_options)


def perform_db_operations(db_options, db_actions, log_level=1, logger=None):
    '''
    Actually perform operations on database.
    Point, we're committing every table action.
    If we have continue_on_error != true, than next table statements are not proceeded
    '''
    try:
        db_conn = get_db_connection(db_options)
        if not db_conn:
            return f"Cannot connect to database due to database module {db_options.get('type')} is not available"
        db_cursor = db_conn.cursor()
    except Exception as e:
        error_msg = f"Database connection failed: {e}"
        if logger:
            logger.error(error_msg)
        return error_msg

    error = ""

    for db_action in db_actions:
        for table, table_actions in db_action.items():
            if log_level >= 1:
                log_msg = f"Performing <{table_actions['type'].upper()}> action on table <{table}>..."
                if logger:
                    logger.info(log_msg)
                else:
                    print(log_msg)

            if table_actions['type'] == 'check':
                try:
                    sql_stmt = form_check_statement(table, table_actions['name'], table_actions['operator'])
                except ValueError as e:
                    error += f"[DATABASE][VALIDATION ERROR]: {e} "
                    if table_actions['continue_on_error']:
                        continue
                    raise Exception(f"[DATABASE][VALIDATION ERROR]: {e}")

                if log_level >= 3:
                    log_msg = f"SQL statement: {sql_stmt} / {table_actions['value']}"
                    if logger:
                        logger.debug(log_msg)
                    else:
                        print(log_msg)

                try:
                    db_cursor.execute(sql_stmt, table_actions['value'])
                    count = db_cursor.fetchone()[0]
                except Exception as e:
                    error += f"[DATABASE][ERROR]: {e} "
                    if table_actions['continue_on_error']:
                        continue
                    db_conn.close()
                    return error

                min_rows, max_rows = parse_row_nums(table_actions['row_nums'])
                if not (min_rows <= count <= max_rows):
                    check_error = f"[DATABASE][CHECK FAILED]: Table `{table}` — expected {table_actions['row_nums']} row(s), got {count} "
                    error += check_error
                    if logger:
                        logger.warning(check_error.strip())
                    if not table_actions['continue_on_error']:
                        db_conn.close()
                        return error
                    continue

                if table_actions['cleanup_after_test']:
                    try:
                        delete_stmt = form_delete_with_operators(table, table_actions['name'], table_actions['operator'])
                        if log_level >= 3:
                            log_msg = f"SQL statement (cleanup): {delete_stmt} / {table_actions['value']}"
                            if logger:
                                logger.debug(log_msg)
                            else:
                                print(log_msg)
                        db_cursor.execute(delete_stmt, table_actions['value'])
                        db_conn.commit()
                    except Exception as e:
                        error += f"[DATABASE][ERROR]: {e} "
                        if not table_actions['continue_on_error']:
                            db_conn.close()
                            return error

                continue

            sql_stmt = None
            try:
                if table_actions['type'] == 'replace':
                    sql_stmt = form_replace_statement(table, table_actions['name'])
                elif table_actions['type'] == 'insert':
                    sql_stmt = form_insert_statement(table, table_actions['name'])
                elif table_actions['type'] == 'delete':
                    sql_stmt = form_delete_statement(table, table_actions['name'])
            except ValueError as e:
                error += f"[DATABASE][VALIDATION ERROR]: {e} "
                if table_actions['continue_on_error']:
                    continue
                raise Exception(f"[DATABASE][VALIDATION ERROR]: {e}")

            if sql_stmt is None:
                continue

            if log_level >= 3:
                log_msg = f"SQL statement: {sql_stmt} / {table_actions['value']}"
                if logger:
                    logger.debug(log_msg)
                else:
                    print(log_msg)

            try:
                db_cursor.execute(sql_stmt, table_actions['value'])
                db_conn.commit()
            except Exception as e:
                error += f"[DATABASE][ERROR]:{e} "
                if table_actions['continue_on_error']:
                    continue
                # Error occurred - exiting
                db_conn.close()
                return error

    db_conn.close()
    return error


def _validate_identifier(identifier):
    """
    Validate SQL identifier (table name, column name) to prevent SQL injection.
    Only allows alphanumeric characters, underscores, and dots.
    """
    if not identifier:
        return False
    # Allow alphanumeric, underscore, and dot (for schema.table notation)
    if not re.match(r'^[a-zA-Z0-9_\.]+$', identifier):
        return False
    # Check for reserved keywords (basic list, extend as needed)
    reserved_words = {
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'UNION', 'WHERE', 'ORDER', 'GROUP', 'HAVING', 'FROM', 'JOIN'
    }
    if identifier.upper() in reserved_words:
        return False
    return True


def form_insert_statement(table, fields):
    """
    Form INSERT statement with proper validation to prevent SQL injection.
    """
    if not _validate_identifier(table):
        raise ValueError(f"Invalid table name: {table}")

    for field in fields:
        if not _validate_identifier(field):
            raise ValueError(f"Invalid field name: {field}")

    sql = f"INSERT INTO `{table}` ("
    sql += "`" + "`,`".join(fields) + "`"
    sql += ") VALUES ("
    sql += ",".join(['%s'] * len(fields))
    sql += ")"

    return sql


def form_replace_statement(table, fields):
    """
    Form REPLACE statement with proper validation to prevent SQL injection.
    """
    if not _validate_identifier(table):
        raise ValueError(f"Invalid table name: {table}")

    for field in fields:
        if not _validate_identifier(field):
            raise ValueError(f"Invalid field name: {field}")

    sql = f"REPLACE INTO `{table}` ("
    sql += "`" + "`,`".join(fields) + "`"
    sql += ") VALUES ("
    sql += ",".join(['%s'] * len(fields))
    sql += ")"

    return sql


def form_delete_statement(table, fields):
    """
    Form DELETE statement with proper validation to prevent SQL injection.
    """
    if not _validate_identifier(table):
        raise ValueError(f"Invalid table name: {table}")

    for field in fields:
        if not _validate_identifier(field):
            raise ValueError(f"Invalid field name: {field}")

    sql = f"DELETE FROM `{table}` WHERE "
    for field in fields:
        sql += f"`{field}` = %s AND "
    sql += "1 = 1"

    return sql


def parse_row_nums(row_nums_str):
    """Parse '1' -> (1, 1), '1-3' -> (1, 3)."""
    s = str(row_nums_str).strip()
    if '-' in s:
        lo, hi = s.split('-', 1)
        return int(lo), int(hi)
    n = int(s)
    return n, n


def _form_where_clause(fields, operators):
    """Form WHERE clause conditions using per-field operators ('=' or 'LIKE')."""
    parts = [f"`{f}` {op} %s" for f, op in zip(fields, operators)]
    parts.append("1 = 1")
    return " AND ".join(parts)


def form_check_statement(table, fields, operators):
    """
    Form SELECT COUNT(*) statement for row existence check.
    Fields whose value contains '%' use LIKE; others use =.
    """
    if not _validate_identifier(table):
        raise ValueError(f"Invalid table name: {table}")
    for field in fields:
        if not _validate_identifier(field):
            raise ValueError(f"Invalid field name: {field}")
    return f"SELECT COUNT(*) FROM `{table}` WHERE {_form_where_clause(fields, operators)}"


def form_delete_with_operators(table, fields, operators):
    """
    Form DELETE statement using per-field operators.
    Used for cleanup after a successful check (supports LIKE for wildcard conditions).
    """
    if not _validate_identifier(table):
        raise ValueError(f"Invalid table name: {table}")
    for field in fields:
        if not _validate_identifier(field):
            raise ValueError(f"Invalid field name: {field}")
    return f"DELETE FROM `{table}` WHERE {_form_where_clause(fields, operators)}"


_TOKEN_RE = re.compile(r'\{(test_start|test_end)(?::([^}]+))?\}')
_DEFAULT_TS_FMT = '%Y-%m-%d %H:%M:%S'
_OP_MAP = {
    '-eq':   '=',
    '-ne':   '!=',
    '-lt':   '<',
    '-le':   '<=',
    '-gt':   '>',
    '-ge':   '>=',
    '-like': 'LIKE',
}


def _parse_ts(s):
    """Parse a timestamp string from env var into a datetime, or return None."""
    if not s:
        return None
    for fmt in (_DEFAULT_TS_FMT, '%Y-%m-%dT%H:%M:%S'):
        try:
            return _dt.strptime(s, fmt)
        except ValueError:
            pass
    return None


def parse_field_value(value):
    """
    Parse a field value that may be prefixed with a bash-style operator flag.

    Recognised flags (must be followed by a space and a non-empty value):
      -eq -> =    -ne -> !=
      -lt -> <    -le -> <=
      -gt -> >    -ge -> >=
      -like -> LIKE

    A flag with no trailing space (e.g. "-ge" alone) is treated as a literal value
    with '=' — consistent with the rule "only operator specified means -eq <value>".
    If no flag is present and the value contains '%', LIKE is used automatically.

    Returns (sql_operator, actual_value).
    """
    for flag, sql_op in _OP_MAP.items():
        if value.startswith(flag + ' '):
            return sql_op, value[len(flag) + 1:]
    if '%' in value:
        return 'LIKE', value
    return '=', value


def substitute_time_tokens(value, start_dt, end_dt):
    """
    Replace {test_start} / {test_end} tokens in a field value.
    Optional strftime format: {test_start:%Y-%m-%d %H:%M} — defaults to _DEFAULT_TS_FMT.
    Returns the original string unchanged for tokens whose datetime is unavailable.
    """
    def _replace(m):
        which, fmt = m.group(1), m.group(2) or _DEFAULT_TS_FMT
        dt = start_dt if which == 'test_start' else end_dt
        return dt.strftime(fmt) if dt else m.group(0)
    return _TOKEN_RE.sub(_replace, value)


def write_report(filename, report):
    report['status'] = "PASS"

    error = report.get("error", "")
    if len(error) > 0:
        report['status'] = "FAIL"

    report_line = json.dumps(report)
    report_line += "\n"

    filename_path = f"/output/{filename}"
    try:
        with open(filename_path, "a") as f_report:
            f_report.write(report_line)
    except (IOError, OSError) as e:
        print(f"Warning: Could not write report to {filename_path}: {e}")


# SCRIPT START
scenario_name = os.environ.get("SCENARIO")
# stage can be pre - running before voip_patrol to populate database and post - to clean up.
scenario_stage = os.environ.get("STAGE", "pre")
report_file = os.environ.get("RESULT_FILE", "database.jsonl")

test_start_dt = _parse_ts(os.environ.get("TEST_START_TIME", ""))
test_end_dt = _parse_ts(os.environ.get("TEST_END_TIME", ""))

# Initialize logging
log_level = get_log_level()
logger = setup_logger(__name__, log_level)
error_reporter = ErrorReporter(logger)

logger.info(f"Starting database operations for scenario: {scenario_name}, stage: {scenario_stage}")
logger.debug(f"Report file: {report_file}, Log level: {log_level}")

scenario_file = f"/xml/{scenario_name}.xml"
if not os.path.exists(scenario_file):
    logger.info(f"Database scenario file is absent for {scenario_name}/{scenario_stage}, skipping...")
    sys.exit(0)

report = {}
report['scenario'] = scenario_name
report['stage'] = scenario_stage
report['error'] = ''

try:
    tree = ET.parse(scenario_file)
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
    if scenario_root[0].tag != 'actions':
        report['error'] = "Scenario missing <actions>, exiting..."
        write_report(report_file, report)
        sys.exit(1)
except Exception as e:
    report['error'] = f"Scenario missing <actions>, exiting... {e}"
    write_report(report_file, report)
    sys.exit(1)

actions = scenario_root[0]

for action in actions:
    if action.tag != 'action':
        print(f"Tag {action.tag} is not supported, skipping ...")
        continue

    action_db_name = action.attrib.get('database', 'default')
    action_stage = action.attrib.get('stage', 'pre')

    if log_level >= 1:
        print(f"Processing actions on database <{action_db_name}>...")

    # info section is holding database credentials by design
    db_info = action.find('info')
    if db_info is None:
        print(f"No info on database is found, ignoring entry {action_db_name}...")
        continue

    db_type = db_info.attrib.get('type', 'mysql')
    if db_type.lower() not in ('mysql', 'pgsql'):
        print(f"At the moment only MySQL/PostgreSQL are supported, ignoring entry {action_db_name}...")
        continue

    # On which database are we performing actions.
    db_base = db_info.attrib.get('base')
    if not db_base :
        print(f"Database for actions is not specified, ignoring entry {action_db_name}...")
        continue

    db_options = {
        'host':     db_info.attrib.get('host', 'localhost'),
        'port':     db_info.attrib.get('port', '3306'),
        'user':     db_info.attrib.get('user', 'root'),
        'password': db_info.attrib.get('password', ''),
        'db':       db_base,
        'type':     db_type.lower(),
    }

    db_actions = []

    for table in action:
        db_action = {}

        table_name = table.attrib.get('name')
        if table.tag != 'table' or not table_name:
            continue

        # Action on table must be explicit
        table_action = table.attrib.get('type', 'none').lower()

        if table_action not in ['replace', 'insert', 'delete', 'check']:
            print(f"Type of action is only 'replace', 'insert', 'delete' and 'check', ignoring entry on {table_name}...")
            continue

        cleanup_after_test = table.attrib.get('cleanup_after_test', 'false').lower()
        is_cleanup = cleanup_after_test in ('true', 'on', '1')

        if table_action == 'check':
            # check only runs in its declared stage; cleanup is handled inline after the check passes
            if action_stage != scenario_stage:
                continue
        else:
            # Possibly not our stage. If we're in pre stage and scenario is only for post - ignore it
            # If we're in post stage and specified cleanup_after_test == true = revert table actions
            if action_stage != scenario_stage and not (action_stage == 'pre' and scenario_stage == 'post' and is_cleanup):
                continue

            # Adjust post stage actions in a case if set cleanup_after_test
            if is_cleanup and scenario_stage == 'post':
                table_action = 'delete' if table_action in ('replace', 'insert') else 'replace'

        continue_on_error = table.attrib.get('continue_on_error', 'false').lower()
        continue_on_error = True if continue_on_error.lower() in ('true', 'on', '1') else False

        if table_action == 'check':
            db_action[table_name] = {
                'type':                 'check',
                'name':                 [],
                'value':                [],
                'operator':             [],
                'row_nums':             table.attrib.get('row_nums', '1'),
                'cleanup_after_test':   is_cleanup,
                'continue_on_error':    continue_on_error,
            }
        else:
            db_action[table_name] = {
                'type':                 table_action,
                'name':                 [],
                'value':                [],
                'continue_on_error':    continue_on_error,
            }

        for field in table:
            if field.tag != 'field':
                continue

            field_name = field.attrib.get('name')
            field_value = field.attrib.get('value')

            if not (field_name and field_value):
                continue

            if table_action == 'check':
                field_value = substitute_time_tokens(field_value, test_start_dt, test_end_dt)
                operator, field_value = parse_field_value(field_value)
                db_action[table_name]['operator'].append(operator)
            db_action[table_name]['name'].append(field_name)
            db_action[table_name]['value'].append(field_value)

        db_actions.append(db_action)

    try:
        report['error'] += perform_db_operations(db_options, db_actions, log_level, logger)
    except Exception as e:
        error_string = f"[DATABASE][ERROR]: {e}"
        report['error'] = error_string
        error_reporter.add_error(error_string, e)
        break

write_report(report_file, report)

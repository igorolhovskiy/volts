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

    return db_handler.connect(
            user=db_options['user'],
            password=db_options['password'],
            host=db_options['host'],
            port=int(db_options['port']),
            database=db_options['db'],
            connect_timeout=5,
            read_timeout=10,
            write_timeout=10
        )


def preform_db_operations(db_options, db_actions, log_level = 1):
    '''
    Actually preform operations on database.
    Point, we're committing every table action.
    If we have continue_on_error != true, than next table statements are not proceeded
    '''
    db_conn = get_db_connection(db_options)
    if not db_conn:
        return f"Cannot connect to database due to database module {db_options.get('type')} is not available"
    db_cursor = db_conn.cursor()
    error = ""

    for db_action in db_actions:
        for table, table_actions in db_action.items():
            if log_level >= 1:
                print(f"Preforming <{table_actions['type'].upper()}> action on table <{table}>...")

            sql_stmt = None
            if table_actions['type'] == 'replace':
                sql_stmt = form_replace_statement(table, table_actions['name'])
            elif table_actions['type'] == 'insert':
                sql_stmt = form_insert_statement(table, table_actions['name'])
            elif table_actions['type'] == 'delete':
                sql_stmt = form_delete_statement(table, table_actions['name'])

            if sql_stmt is None:
                continue

            if log_level >= 3:
                print(f"SQL statement: {sql_stmt} / {table_actions['value']}")

            try:
                db_cursor.execute(sql_stmt, table_actions['value'])
                db_conn.commit()
            except Exception as e:
                error += f"[DATABASE][ERROR]:{e} "
                if table_actions['continue_on_error']:
                    continue
                raise Exception(f"[DATABASE][ERROR]: Problem with action {sql_stmt} on table {table}: {e}")

    db_conn.close()
    return error


def form_insert_statement(table, fields):
    sql = f"INSERT INTO {table} ("
    sql += "`" + "`,`".join(fields) + "`"
    sql += ") VALUES ("
    sql += ",".join(['%s'] * len(fields))
    sql += ")"

    return sql


def form_replace_statement(table, fields):
    sql = f"REPLACE INTO {table} ("
    sql += "`" + "`,`".join(fields) + "`"
    sql += ") VALUES ("
    sql += ",".join(['%s'] * len(fields))
    sql += ")"

    return sql


def form_delete_statement(table, fields):
    sql = f"DELETE FROM {table} WHERE "
    for field in fields:
        sql += f"`{field}` = %s AND "
    sql += "1 = 1"

    return sql


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


# SCRIPT START
scenario_name = os.environ.get("SCENARIO")
# sage can be pre - running before voip_patrol to populate database and post - to clean up.
scenario_stage = os.environ.get("STAGE", "pre")
# Log level for the console
try:
    log_level = int(os.environ.get("LOG_LEVEL", "1"))
except ValueError:
    log_level = 1

report_file = os.environ.get("RESULT_FILE", "database.jsonl")

scenario_file = f"/xml/{scenario_name}.xml"
if not os.path.exists(scenario_file):
    print(f"Database scenario file is absent for {scenario_name}/{scenario_stage}, skipping...")
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

    # On which database are we preforming actions.
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
        table_action = table.attrib.get('type', 'none')

        if table_action not in ['replace', 'insert', 'delete']:
            print(f"Type of action is only 'replace', 'insert' and 'delete', ignoring entry on {table_name}...")
            continue

        cleanup_after_test = table.attrib.get('cleanup_after_test', 'false')
        is_cleanup = cleanup_after_test in ['true', 'on', '1']

        # Possibly not our stage. If we're in pre stage and scenario is only for post - ignore it
        # If we're in post stage and specified cleanup_after_test == true = revert table actions
        if action_stage != scenario_stage and not (action_stage == 'pre' and scenario_stage == 'post' and is_cleanup):
            continue

        # Adjust post stage actions in a case if set cleanup_after_test
        if is_cleanup and scenario_stage == 'post':
            table_action = 'delete' if table_action in ['replace', 'insert'] else 'replace'

        continue_on_error = table.attrib.get('continue_on_error', 'false')
        continue_on_error = True if continue_on_error.lower() in ['true', 'on', '1'] else False

        db_action[table_name] = {
            'type':                 table_action,
            'name':                 [],
            'value':                [],
            'continue_on_error':    continue_on_error,
        }

        field_names = []
        field_values = []

        for field in table:
            if field.tag != 'field':
                continue

            field_name = field.attrib.get('name')
            field_value = field.attrib.get('value')

            if not (field_name and field_value):
                continue

            db_action[table_name]['name'].append(field_name)
            db_action[table_name]['value'].append(field_value)

        db_actions.append(db_action)

    try:
        report['error'] += preform_db_operations(db_options, db_actions, log_level)
    except Exception as e:
        error_string = f"[DATABASE][ERROR]: {e}"
        report['error'] = error_string
        print(error_string)
        break

write_report(report_file, report)

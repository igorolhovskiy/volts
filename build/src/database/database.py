# Script to read XML scenario for database
# and preform actions on them. Multiple databases/tables are supported within 1 scenario
#
# Example of processed XML insering data in subsriber table
#
# <config>
#     <actions>
#         <action database="kamdb" stage="pre">
#             <table cleanup_after_test="true" name="subscriber" type="insert">
#                 <field name="username" value="11111" />
#                 <field name="domain" value="mypbx.com" />
#                 <field name="ha1" value="b509095666231146d2650fe1cc1265ec" />
#                 <field name="password" value="dummy_data_here" />
#             </table>
#             <info base="kamailio"
#                 host="my_kamailio.host"
#                 password="superSecretDBPassword"
#                 type="mysql"
#                 user="kamailiorw" />
#         </action>
#     </actions>
# </config>
#
# on stage "pre"
# USE kamailio;
# INSERT INTO subscriber (username, domain, ha1, password) VALUES ("11111", "mypbx.com", "b509095666231146d2650fe1cc1265ec", "dummy_data_here");
#
# on stage "post"
# USE kamailio;
# DELETE FROM subscriber WHERE username = "11111" AND domain = "mypbx.com" AND ha1 = "b509095666231146d2650fe1cc1265ec" AND password = "dummy_data_here";
#
# That simple

import xml.etree.ElementTree as ET
import sys
import os

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

def preform_db_operations(db_options, db_actions):
    '''
    Actually preform operations on database.
    Point, we're committing every table action.
    If we have ignore_on_error != true, than next table statements are not proceeded
    '''
    db_conn = get_db_connection(db_options)
    db_cursor = db_conn.cursor()

    for db_action in db_actions:
        for table, table_actions in db_action.items():
            print("Preforming <{}> action on table <{}>...".format(table_actions['type'].upper(), table))

            sql_stmt = None
            if table_actions['type'] == 'replace':
                sql_stmt = form_replace_statement(table, table_actions['name'])
            elif table_actions['type'] == 'insert':
                sql_stmt = form_insert_statement(table, table_actions['name'])
            elif table_actions['type'] == 'delete':
                sql_stmt = form_delete_statement(table, table_actions['name'])

            if sql_stmt is None:
                continue

            # print("Executing {} with {}".format(sql_stmt, table_actions['value']))
            try:
                db_cursor.execute(sql_stmt, table_actions['value'])
                db_conn.commit()
            except Exception as e:
                if table_actions['ignore_on_error']:
                    continue
                raise Exception("[DATABASE][ERROR]: Problem with action {} on table {}: {}".format(sql_stmt, table, e))

    db_conn.close()

def form_insert_statement(table, fields):
    sql  = "INSERT INTO {} (".format(table)
    sql += ",".join(fields)
    sql += ") VALUES ("
    sql += ",".join(['%s'] * len(fields))
    sql += ")"

    return sql

def form_replace_statement(table, fields):
    sql  = "REPLACE INTO {} (".format(table)
    sql += ",".join(fields)
    sql += ") VALUES ("
    sql += ",".join(['%s'] * len(fields))
    sql += ")"

    return sql

def form_delete_statement(table, fields):
    sql = "DELETE FROM {} WHERE ".format(table)
    for field in fields:
        sql += "{} = %s AND ".format(field)
    sql += "1 = 1"

    return sql

### SCRIPT START
scenario_name = os.environ.get("SCENARIO")
# sage can be pre - running before voip_patrol to populate database and post - to clean up.
scenario_stage = os.environ.get("STAGE", "pre")


scenario_file = '/xml/{}.xml'.format(scenario_name)
if not os.path.exists(scenario_file):
    print("Database scenario file is absent for {}/{}, skipping...".format(scenario_name, scenario_stage))
    sys.exit(0)

try:
    tree = ET.parse(scenario_file)
    scenario_root = tree.getroot()
except Exception as e:
    print("Problem parsing {}:{}".format(scenario_name, e))
    sys.exit(1)

if scenario_root.tag != 'config':
    print("Scenario root tag is not <config>, exiting...")
    sys.exit(1)

if scenario_root[0].tag != 'actions':
    print("Scenario missing <actions>, exiting...")
    sys.exit(1)

actions = scenario_root[0]

for action in actions:
    if action.tag != 'action':
        print("Tag {} is not supported, skipping ...".format(action.tag))
        continue

    action_db_name = action.attrib.get('database', 'default')
    action_stage = action.attrib.get('stage', 'pre')

    print("Processing actions on database <{}>...".format(action_db_name))

    # info section is holding database credentials by design
    db_info = action.find('info')
    if db_info is None:
        print("No info on database is found, ignoring entry {}...".format(action_db_name))
        continue

    db_type = db_info.attrib.get('type', 'mysql')
    if db_type.lower() not in ['mysql', 'pgsql']:
        print("At the moment only MySQL/PostgreSQL are supported, ignoring entry {}...".format(action_db_name))
        continue

    # On which database are we preforming actions.
    db_base = db_info.attrib.get('base')
    if not db_base :
        print("Database for actions is not specified, ignoring entry {}...".format(action_db_name))
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
            print("Type of action is only 'replace', 'insert' and 'delete', ignoring entry on {}...".format(table_name))
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

        ignore_on_error = table.attrib.get('ignore_on_error', 'false')
        ignore_on_error = True if ignore_on_error.lower() in ['true', 'on', '1'] else False

        db_action[table_name] = {
            'type'  :           table_action,
            'name'  :           [],
            'value' :           [],
            'ignore_on_error':  ignore_on_error,
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
        preform_db_operations(db_options, db_actions)
    except Exception as e:
        print("[DATABASE][ERROR]: {}".format(e))

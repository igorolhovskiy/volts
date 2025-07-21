#!/bin/bash
# Main user controlled variables
# Report type to provide
REPORT_TYPE='table_full'
# Log level on console
LOG_LEVEL=0
# Timezone
TIMEZONE=`timedatectl | grep 'Time zone' | cut -d ':' -f 2 | awk '{ print $1 }'`
# Maximum time single test is allowed to run in seconds. (10 min)
MAX_SINGLE_TEST_TIME=600

# TLS-WSS proxy port parameters, change them only if you know what you are doing
OPENSIPS_TLS_PORT=6051
OPENSIPS_WSS_PORT=9443
# HEP Source port
OPENSIPS_HEPS_PORT=8887
# HEP Destination port
OPENSIPS_HEPD_PORT=8888

print_running_char() {
    case "${rc}" in
        "-"|".-")
            rc="\\"
            ;;
        "\\")
            rc="|"
            ;;
        "|")
            rc="/"
            ;;
        "/")
            rc=".-"
            ;;
    esac
    echo -en "\b \b${rc}"
}

wait_background_container() {
    # Declare counter(i), process_counter(pc) and running_character(rc)
    i=0
    pc=`docker ps | grep ${1} | wc -l`
    rc='-'
    echo -n "Running ${CURRENT_SCENARIO} ${2} ${rc}"

    TIME_TEST_START=`date +%s`
    ERROR_STRING=""
    MAX_CYCLES=$(( ${MAX_SINGLE_TEST_TIME} * 2 ))
    # Limit with maximum time
    while [ $i -le ${MAX_CYCLES} ] && [ $pc -ge 1 ]; do
        ((i++))
        sleep 0.5
        pc=`docker ps | grep ${1} | wc -l`
        print_running_char
    done

    if [ $pc -ge 1 ]; then
        docker stop ${1} >> /dev/null
        ERROR_STRING="\n[WARNING] Container ${1} was forcefully stopped"
    fi

    TIME_TEST_END=`date +%s`
    echo -e "\b\b  \b\b. Done in $((${TIME_TEST_END} - ${TIME_TEST_START}))s${ERROR_STRING}"
}

control_opensips() {
    if [ "${1}" = "start" ]; then
        echo "Websocket proxy starting...  "
        docker run --name=${PROXY_CONTAINER_NAME} \
            --env OPENSIPS_TLS_PORT=`echo ${OPENSIPS_TLS_PORT}` \
            --env OPENSIPS_WSS_PORT=`echo ${OPENSIPS_WSS_PORT}` \
            --env OPENSIPS_HEPS_PORT=`echo ${OPENSIPS_HEPS_PORT}` \
            --env OPENSIPS_HEPD_PORT=`echo ${OPENSIPS_HEPD_PORT}` \
            --env VP_TLS_PORT=`echo $[${VP_PORT} + 1]` \
            --net=host \
            --rm \
            -d \
            ${PROXY_IMAGE} >> /dev/null
        # Give a time to start the container and push it a bit
        sleep 1
        cleanup_opensips_cache
    else
        echo "Websocket proxy stopping..."
        docker stop ${PROXY_CONTAINER_NAME} >> /dev/null 2>&1
    fi
}

run_voip_patrol() {
    if [ ! -f "${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/voip_patrol.xml" ]; then
        return
    fi

    BG_RUN=""
    OUT_REDIRECT=""
    if [ ${LOG_LEVEL} -eq 0 ]; then
        BG_RUN="-d"
        OUT_REDIRECT=">> /dev/null"
    fi

    docker rm ${VP_CONTAINER_NAME} >> /dev/null 2>&1

    eval docker run --name=${VP_CONTAINER_NAME} \
        --env XML_CONF=`echo ${CURRENT_SCENARIO}` \
        --env PORT=`echo ${VP_PORT}` \
        --env RESULT_FILE=`echo ${VP_RESULT_FILE}` \
        --env LOG_LEVEL=`echo ${LOG_LEVEL}` \
        --env LOG_LEVEL_FILE=`echo ${LOG_LEVEL_FILE}` \
        --env TZ=`echo ${TIMEZONE}` \
        --volume ${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/voip_patrol.xml:/xml/${CURRENT_SCENARIO}.xml \
        --volume ${DIR_PREFIX}/tmp/output:/output \
        --volume ${DIR_PREFIX}/voice_ref_files:/voice_ref_files \
        --net=host \
        --rm \
        ${BG_RUN} \
        ${VP_IMAGE} ${OUT_REDIRECT}

    if [ ${LOG_LEVEL} -eq 0 ]; then
        wait_background_container ${VP_CONTAINER_NAME} voip_patrol
    fi
}

run_prepare() {
    docker run --name=${P_CONTAINER_NAME} \
        --env SCENARIO_NAME=`echo ${SCENARIO}` \
        --env OPENSIPS_TLS_PORT=`echo ${OPENSIPS_TLS_PORT}` \
        --env LOG_LEVEL=`echo ${LOG_LEVEL}` \
        --env TAG=`echo ${PREPARE_TAG}` \
        --env TZ=`echo ${TIMEZONE}` \
        --volume ${DIR_PREFIX}/scenarios:/opt/input/ \
        --volume ${DIR_PREFIX}/tmp/input:/opt/output \
        --net=none \
        --rm \
        ${P_IMAGE}
}

run_report() {
    docker run --name=${R_CONTAINER_NAME} \
        --env VP_RESULT_FILE=`echo ${VP_RESULT_FILE}` \
        --env D_RESULT_FILE=`echo ${D_RESULT_FILE}` \
        --env M_RESULT_FILE=`echo ${M_RESULT_FILE}` \
        --env SIPP_RESULT_FILE=`echo ${SIPP_RESULT_FILE}` \
        --env REPORT_TYPE=`echo ${REPORT_TYPE}` \
        --env TZ=`echo ${TIMEZONE}` \
        --volume ${DIR_PREFIX}/tmp/input:/opt/scenarios/ \
        --volume ${DIR_PREFIX}/tmp/output:/opt/report \
        --net=none \
        --rm \
        ${R_IMAGE}
}

run_database() {
    if [ ! -f "${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/database.xml" ]; then
        return
    fi

    eval docker run --name=${D_CONTAINER_NAME} \
        --env SCENARIO=`echo ${CURRENT_SCENARIO}` \
        --env RESULT_FILE=`echo ${D_RESULT_FILE}` \
        --env LOG_LEVEL=`echo ${LOG_LEVEL}` \
        --env STAGE=`echo ${1}` \
        --env TZ=`echo ${TIMEZONE}` \
        --volume ${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/database.xml:/xml/${CURRENT_SCENARIO}.xml \
        --volume ${DIR_PREFIX}/tmp/output:/output \
        --rm \
        ${D_IMAGE}
}

run_sipp() {
    if [ ! -f "${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/sipp.xml" ]; then
        return
    fi

    BG_RUN=""
    OUT_REDIRECT=""
    if [ ${LOG_LEVEL} -eq 0 ]; then
        BG_RUN="-d"
        OUT_REDIRECT=">> /dev/null"
    fi

    eval docker run --name=${SIPP_CONTAINER_NAME} \
        --env SCENARIO=`echo ${CURRENT_SCENARIO}` \
        --env RESULT_FILE=`echo ${SIPP_RESULT_FILE}` \
        --env LOG_LEVEL=`echo ${LOG_LEVEL}` \
        --volume ${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/sipp.xml:/xml/${CURRENT_SCENARIO}.xml \
        --volume ${DIR_PREFIX}/tmp/output:/output \
        --rm \
        ${BG_RUN} \
        ${SIPP_IMAGE} ${OUT_REDIRECT}

    if [ ${LOG_LEVEL} -eq 0 ]; then
        wait_background_container ${SIPP_CONTAINER_NAME} sipp
    fi
}

run_media() {
    if [ ! -f "${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/media_check.xml" ]; then
        return
    fi

    docker run --name=${M_CONTAINER_NAME} \
        --env SCENARIO=`echo ${CURRENT_SCENARIO}` \
        --env RESULT_FILE=`echo ${M_RESULT_FILE}` \
        --env LOG_LEVEL=`echo ${LOG_LEVEL}` \
        --volume ${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/media_check.xml:/xml/${CURRENT_SCENARIO}.xml \
        --volume ${DIR_PREFIX}/tmp/output:/output \
        --net=none \
        --rm \
        ${M_IMAGE}
}

cleanup_opensips_cache() {
    docker exec ${PROXY_CONTAINER_NAME} /usr/bin/opensips-cli -x mi cache_remove_chunk "*" >> /dev/null 2>&1
}

delete_containers() {
    docker stop ${M_CONTAINER_NAME} >> /dev/null 2>&1
    docker stop ${SIPP_CONTAINER_NAME} >> /dev/null 2>&1
    docker stop ${D_CONTAINER_NAME} >> /dev/null 2>&1
    docker stop ${R_CONTAINER_NAME} >> /dev/null 2>&1
    docker stop ${P_CONTAINER_NAME} >> /dev/null 2>&1
    docker stop ${VP_CONTAINER_NAME} >> /dev/null 2>&1
    docker stop ${PROXY_CONTAINER_NAME} >> /dev/null 2>&1

    docker rm ${M_CONTAINER_NAME} >> /dev/null 2>&1
    docker rm ${SIPP_CONTAINER_NAME} >> /dev/null 2>&1
    docker rm ${D_CONTAINER_NAME} >> /dev/null 2>&1
    docker rm ${R_CONTAINER_NAME} >> /dev/null 2>&1
    docker rm ${P_CONTAINER_NAME} >> /dev/null 2>&1
    docker rm ${VP_CONTAINER_NAME} >> /dev/null 2>&1
    docker rm ${PROXY_CONTAINER_NAME} >> /dev/null 2>&1
}

run_scenario() {
    run_database pre
    run_voip_patrol
    run_sipp
    run_database post
    run_media
    if [ -f ${DIR_PREFIX}/tmp/input/websocket.need ]; then
        cleanup_opensips_cache
    fi
}


# Help function
show_help() {
    cat << EOF
VOLTS (Voip Open Linear Tester Suite) - VoIP Functional Testing Framework

Usage: $0 [OPTIONS] [SCENARIO]

SCENARIO:
    <scenario_name>     Run specific scenario (e.g., 001-register or scenarios/001-register.xml)
    tag=<tags>          Run scenarios with specific tags (e.g., tag=set1,set2)
    stop                Stop tests and delete all containers
    sngrep              Launch SIP packet capture tool
    dbclean             Clean up test data from databases

OPTIONS:
    -h, --help          Show this help message
    -l, --log-level N   Set log level (0=silent, 1=normal, 2=verbose, 3=debug) [default: $LOG_LEVEL]
    -r, --report TYPE   Set report type (table|json|table_full|json_full) [default: $REPORT_TYPE]
    -t, --timeout N     Set maximum single test time in seconds [default: $MAX_SINGLE_TEST_TIME]
    -v, --verbose       Enable verbose output (equivalent to -l 2)
    -d, --debug         Enable debug output (equivalent to -l 3)
    --tls-port N        Set OpenSIPS TLS port [default: $OPENSIPS_TLS_PORT]
    --wss-port N        Set OpenSIPS WSS port [default: $OPENSIPS_WSS_PORT]
    --heps-port N       Set HEP source port [default: $OPENSIPS_HEPS_PORT]
    --hepd-port N       Set HEP destination port [default: $OPENSIPS_HEPD_PORT]

EXAMPLES:
    $0                          Run all scenarios
    $0 001-register             Run specific scenario
    $0 scenarios/001-register.xml  Run specific scenario with full path
    $0 tag=sipp,media           Run scenarios tagged as sipp or media
    $0 -l 3 001-register        Run scenario with debug logging
    $0 -r json -v               Run all scenarios with JSON output and verbose logging
    $0 --timeout 300 001-register  Run scenario with 5-minute timeout
    $0 stop                     Stop all containers
    $0 sngrep                   Launch SIP packet capture
    $0 dbclean                  Clean up databases

ENVIRONMENT VARIABLES:
    REPORT_TYPE         Override default report type
    LOG_LEVEL           Override default log level
    MAX_SINGLE_TEST_TIME Override default timeout

EOF
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -l|--log-level)
                if [[ -n "$2" && "$2" =~ ^[0-3]$ ]]; then
                    LOG_LEVEL="$2"
                    shift 2
                else
                    echo "Error: --log-level requires a number between 0-3" >&2
                    exit 1
                fi
                ;;
            -r|--report)
                if [[ -n "$2" && "$2" =~ ^(table|json|table_full|json_full)$ ]]; then
                    REPORT_TYPE="$2"
                    shift 2
                else
                    echo "Error: --report must be one of: table, json, table_full, json_full" >&2
                    exit 1
                fi
                ;;
            -t|--timeout)
                if [[ -n "$2" && "$2" =~ ^[0-9]+$ ]]; then
                    MAX_SINGLE_TEST_TIME="$2"
                    shift 2
                else
                    echo "Error: --timeout requires a positive number" >&2
                    exit 1
                fi
                ;;
            -v|--verbose)
                LOG_LEVEL=2
                shift
                ;;
            -d|--debug)
                LOG_LEVEL=3
                shift
                ;;
            --tls-port)
                if [[ -n "$2" && "$2" =~ ^[0-9]+$ ]]; then
                    OPENSIPS_TLS_PORT="$2"
                    shift 2
                else
                    echo "Error: --tls-port requires a valid port number" >&2
                    exit 1
                fi
                ;;
            --wss-port)
                if [[ -n "$2" && "$2" =~ ^[0-9]+$ ]]; then
                    OPENSIPS_WSS_PORT="$2"
                    shift 2
                else
                    echo "Error: --wss-port requires a valid port number" >&2
                    exit 1
                fi
                ;;
            --heps-port)
                if [[ -n "$2" && "$2" =~ ^[0-9]+$ ]]; then
                    OPENSIPS_HEPS_PORT="$2"
                    shift 2
                else
                    echo "Error: --heps-port requires a valid port number" >&2
                    exit 1
                fi
                ;;
            --hepd-port)
                if [[ -n "$2" && "$2" =~ ^[0-9]+$ ]]; then
                    OPENSIPS_HEPD_PORT="$2"
                    shift 2
                else
                    echo "Error: --hepd-port requires a valid port number" >&2
                    exit 1
                fi
                ;;
            stop|sngrep|dbclean)
                # Special commands - preserve existing behavior
                if [[ -z "$SCENARIO" ]]; then
                    SCENARIO="$1"
                else
                    echo "Error: Multiple scenarios specified" >&2
                    exit 1
                fi
                shift
                ;;
            tag=*|-tag=*|--tag=*)
                # Tag specification - preserve existing behavior
                if [[ -z "$SCENARIO" ]]; then
                    SCENARIO="$1"
                else
                    echo "Error: Multiple scenarios specified" >&2
                    exit 1
                fi
                shift
                ;;
            -*)
                echo "Error: Unknown option $1" >&2
                echo "Use $0 --help for usage information" >&2
                exit 1
                ;;
            *)
                # Regular scenario name
                if [[ -z "$SCENARIO" ]]; then
                    SCENARIO="$1"
                else
                    echo "Error: Multiple scenarios specified" >&2
                    exit 1
                fi
                shift
                ;;
        esac
    done
}

clean_tmp() {
    rm -rf tmp/input/*
    rm -rf tmp/input/*
}

# Script controlled variables
DIR_PREFIX=`pwd`
SCENARIO=""

# Parse command line arguments
parse_arguments "$@"

mkdir -p tmp/input
mkdir -p tmp/output

# prepare
P_IMAGE=volts_prepare:latest
P_CONTAINER_NAME=volts_prepare

# database
D_IMAGE=volts_database:latest
D_CONTAINER_NAME=volts_database
D_RESULT_FILE="database.jsonl"

# voip_patrol
VP_IMAGE=volts_vp:latest
VP_CONTAINER_NAME=volts_vp
#VP_IMAGE=voip_patrol_local:latest
#VP_CONTAINER_NAME=voip_patrol_local
VP_PORT=5060
VP_RESULT_FILE="voip_patrol.jsonl"
LOG_LEVEL_FILE=${LOG_LEVEL}

# media
M_IMAGE=volts_media:latest
M_CONTAINER_NAME=volts_media
M_RESULT_FILE="media_check.jsonl"

# sipp
SIPP_CONTAINER_NAME=volts_sipp
SIPP_IMAGE=volts_sipp:latest
SIPP_RESULT_FILE="sipp.jsonl"

# opensips
PROXY_CONTAINER_NAME=volts_opensips
PROXY_IMAGE=volts_opensips:latest

# Handle special commands first
if [ "x${SCENARIO}" == "xstop" ]; then
    echo -n "Stopping and deleting containers..."
    delete_containers
    echo " Done"
    exit 0
fi

if [ "x${SCENARIO}" == "xsngrep" ]; then
    if [ `docker ps | grep -c ${PROXY_CONTAINER_NAME}` == 1 ]; then
        echo "Starting sngrep in docker..."
        docker exec -it ${PROXY_CONTAINER_NAME} sngrep -L udp:127.0.0.1:${OPENSIPS_HEPD_PORT}
        echo "Done"
    else
        echo "Cannot find ${PROXY_CONTAINER_NAME}. Make sure you have VOLTS running"
    fi
    exit 0
fi

if [ "x${SCENARIO}" == "xdbclean" ]; then
    echo -n "Cleaning up database(s)"

    clean_tmp
    unset SCENARIO
    run_prepare

    for D in ${DIR_PREFIX}/tmp/input/*; do
        CURRENT_SCENARIO=`basename ${D}`
        run_database post
        echo -n .
    done

    echo " Done."
    exit 0
fi

# Handle tag specification
if [ "`echo ${SCENARIO} | cut -c1-4`" == "tag=" ]; then
    PREPARE_TAG=`echo ${SCENARIO} | cut -c5-`
    unset SCENARIO
elif [ "`echo ${SCENARIO} | cut -c1-5`" == "-tag=" ]; then
    PREPARE_TAG=`echo ${SCENARIO} | cut -c6-`
    unset SCENARIO
elif [ "`echo ${SCENARIO} | cut -c1-6`" == "--tag=" ]; then
    PREPARE_TAG=`echo ${SCENARIO} | cut -c7-`
    unset SCENARIO
fi

# Process scenario name
if [ "x${SCENARIO}" != "x" ]; then
    SCENARIO=`basename ${SCENARIO} | cut -f 1 -d .`
fi

clean_tmp
run_prepare

if [ ! -f ${DIR_PREFIX}/tmp/input/scenarios.done ]; then
    echo "Scenarios are not prepared, please check for the errors"
    exit 1
fi

TIME_TOTAL_START=`date +%s`

rm -f ${DIR_PREFIX}/tmp/output/${D_RESULT_FILE}
rm -f ${DIR_PREFIX}/tmp/output/${M_RESULT_FILE}
rm -f ${DIR_PREFIX}/tmp/output/${VP_RESULT_FILE}
rm -f ${DIR_PREFIX}/tmp/output/${SIPP_RESULT_FILE}
delete_containers

# Start WSS-TLS proxy
if [ -f ${DIR_PREFIX}/tmp/input/websocket.need ]; then
    control_opensips start
fi

if [ -z ${SCENARIO} ]; then
    for D in ${DIR_PREFIX}/tmp/input/*; do
        CURRENT_SCENARIO=`basename ${D}`
        run_scenario
    done
else
    CURRENT_SCENARIO=${SCENARIO}
    run_scenario
fi

# Stop WSS-TLS proxy
if [ -f ${DIR_PREFIX}/tmp/input/websocket.need ]; then
    control_opensips stop
fi

# report
R_IMAGE=volts_report:latest
R_CONTAINER_NAME=volts_report

run_report
delete_containers

TIME_TOTAL_END=`date +%s`
TIME_TOTAL_RUN=$((${TIME_TOTAL_END} - ${TIME_TOTAL_START}))
HMS_TOTAL_RUN=`date -d@${TIME_TOTAL_RUN} -u +%H:%M:%S`
echo "Total time taken: ${HMS_TOTAL_RUN}"

exit 0

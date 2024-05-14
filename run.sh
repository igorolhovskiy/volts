#!/bin/bash
# Main user controlled variables
# Report type to provide
REPORT_TYPE='table_full'
# First argument is the name of the scenario to run. (Optional)
# Log level on console. Can be overrided as 2nd argument passing to the script.
LOG_LEVEL=0
# Timezone
TIMEZONE=`timedatectl | grep 'Time zone' | cut -d ':' -f 2 | awk '{ print $1 }'`
# Maximum time single test is allowed to run in seconds. (2 min)
MAX_SINGLE_TEST_TIME=120

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

    echo -e "\b\b  \b\b. Done in $((i/2))s${ERROR_STRING}"
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
        # Give a time to start the container
        sleep 0.5
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
    cleanup_opensips_cache
}


# Script controlled variables
DIR_PREFIX=`pwd`
# First arument - single test to run
SCENARIO="$1"
# Second argument - default log level
LOG_LEVEL="${2:-${LOG_LEVEL}}"

mkdir -p tmp/input
mkdir -p tmp/output

if [ "x${SCENARIO}" != "x" ]; then
    SCENARIO=`basename ${SCENARIO} | cut -f 1 -d .`
fi

# prepare
P_IMAGE=volts_prepare:latest
P_CONTAINER_NAME=volts_prepare

rm -f tmp/input/scenarios.done
run_prepare

if [ ! -f ${DIR_PREFIX}/tmp/input/scenarios.done ]; then
    echo "Scenarios are not prepared, please check for the errors"
    exit 1
fi

# database
D_IMAGE=volts_database:latest
D_CONTAINER_NAME=volts_database
D_RESULT_FILE="database.jsonl"

# voip_patrol
VP_IMAGE=volts_vp:latest
VP_CONTAINER_NAME=volts_vp
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

rm -f ${DIR_PREFIX}/tmp/output/${D_RESULT_FILE}
rm -f ${DIR_PREFIX}/tmp/output/${M_RESULT_FILE}
rm -f ${DIR_PREFIX}/tmp/output/${VP_RESULT_FILE}
rm -f ${DIR_PREFIX}/tmp/output/${SIPP_RESULT_FILE}
delete_containers

# Start WSS-TLS proxy
control_opensips start

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
control_opensips stop

# report
R_IMAGE=volts_report:latest
R_CONTAINER_NAME=volts_report

run_report
delete_containers
exit 0

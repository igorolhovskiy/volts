#!/bin/bash
# Main user controlled variables
# Report type to provide
REPORT_TYPE='table_full'
# voip_patrol log level on console
VP_LOG_LEVEL=0

# Script controlled variables
DIR_PREFIX=`pwd`
# First arument - single test to run
XML_CONF="$1"

# prepare
P_IMAGE=volts_prepare:latest
P_CONTAINER_NAME=volts_prepare

docker rm ${P_CONTAINER_NAME} >> /dev/null 2>&1
rm -f tmp/input/scenarios.done

docker run --name=${P_CONTAINER_NAME} \
    --env SCENARIO_NAME=`echo ${XML_CONF}` \
    --volume ${DIR_PREFIX}/vp_scenarios:/opt/input/ \
    --volume ${DIR_PREFIX}/tmp/input:/opt/output \
    ${P_IMAGE}

docker rm ${P_CONTAINER_NAME}

if [ ! -f "${DIR_PREFIX}/tmp/input/scenarios.done" ]; then
    echo "Scenarios are not prepared, please check for the errors"
    exit 1
fi

# voip_patrol
VP_IMAGE=volts_vp:latest
VP_CONTAINER_NAME=volts_vp
VP_PORT=5060
VP_RESULT_FILE="result.jsonl"
VP_LOG_LEVEL_FILE=${VP_LOG_LEVEL}

docker rm ${VP_CONTAINER_NAME} >> /dev/null 2>&1
rm -f ${DIR_PREFIX}/tmp/output/${VP_RESULT_FILE}

docker run --net=host \
    --name=${VP_CONTAINER_NAME} \
    --env XML_CONF=`echo ${XML_CONF}` \
    --env PORT=`echo ${VP_PORT}` \
    --env RESULT_FILE=`echo ${VP_RESULT_FILE}` \
    --env LOG_LEVEL=`echo ${VP_LOG_LEVEL}` \
    --env LOG_LEVEL_FILE=`echo ${VP_LOG_LEVEL_FILE}` \
    --volume ${DIR_PREFIX}/tmp/input:/xml \
    --volume ${DIR_PREFIX}/tmp/output:/output \
    --volume ${DIR_PREFIX}/voice_ref_files:/voice_ref_files \
    ${VP_IMAGE}

docker rm ${VP_CONTAINER_NAME}

# report
R_IMAGE=volts_report:latest
R_CONTAINER_NAME=volts_report

docker rm ${R_CONTAINER_NAME} >> /dev/null 2>&1

docker run --name=${R_CONTAINER_NAME} \
    --env REPORT_FILE=`echo ${VP_RESULT_FILE}` \
    --env REPORT_TYPE=`echo ${REPORT_TYPE}` \
    --volume ${DIR_PREFIX}/tmp/input:/opt/scenarios/ \
    --volume ${DIR_PREFIX}/tmp/output:/opt/report \
    ${R_IMAGE}

docker rm ${R_CONTAINER_NAME} >> /dev/null 2>&1

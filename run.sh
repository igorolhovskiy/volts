#!/bin/bash
# Main user controlled variables
# Report type to provide
REPORT_TYPE='table_full'
# voip_patrol log level on console
VP_LOG_LEVEL=0
# Timezone
TIMEZONE=`timedatectl | grep "Time zone" | awk '{print $3}'`

run_voip_patrol() {
    docker rm ${VP_CONTAINER_NAME} >> /dev/null 2>&1

    if [ ! -f "${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/voip_patrol.xml" ]; then
        return
    fi

    docker run --net=host \
    --name=${VP_CONTAINER_NAME} \
    --env XML_CONF=`echo ${CURRENT_SCENARIO}` \
    --env PORT=`echo ${VP_PORT}` \
    --env RESULT_FILE=`echo ${VP_RESULT_FILE}` \
    --env LOG_LEVEL=`echo ${VP_LOG_LEVEL}` \
    --env LOG_LEVEL_FILE=`echo ${VP_LOG_LEVEL_FILE}` \
    --env TZ=`echo ${TIMEZONE}` \
    --volume ${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/voip_patrol.xml:/xml/${CURRENT_SCENARIO}.xml \
    --volume ${DIR_PREFIX}/tmp/output:/output \
    --volume ${DIR_PREFIX}/voice_ref_files:/voice_ref_files \
    ${VP_IMAGE}

    docker rm ${VP_CONTAINER_NAME}
}

run_prepare() {
    docker rm ${P_CONTAINER_NAME} >> /dev/null 2>&1

    docker run --name=${P_CONTAINER_NAME} \
        --env SCENARIO_NAME=`echo ${SCENARIO}` \
        --env TZ=`echo ${TIMEZONE}` \
        --volume ${DIR_PREFIX}/scenarios:/opt/input/ \
        --volume ${DIR_PREFIX}/tmp/input:/opt/output \
        ${P_IMAGE}

    docker rm ${P_CONTAINER_NAME}
}

run_report() {
    docker rm ${R_CONTAINER_NAME} >> /dev/null 2>&1

    docker run --name=${R_CONTAINER_NAME} \
        --env VP_RESULT_FILE=`echo ${VP_RESULT_FILE}` \
        --env D_RESULT_FILE=`echo ${D_RESULT_FILE}` \
        --env REPORT_TYPE=`echo ${REPORT_TYPE}` \
        --env TZ=`echo ${TIMEZONE}` \
        --volume ${DIR_PREFIX}/tmp/input:/opt/scenarios/ \
        --volume ${DIR_PREFIX}/tmp/output:/opt/report \
        ${R_IMAGE}

    docker rm ${R_CONTAINER_NAME} >> /dev/null 2>&1
}

run_database() {
    docker rm ${D_CONTAINER_NAME} >> /dev/null 2>&1

    if [ ! -f "${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/database.xml" ]; then
        return
    fi

    docker run --name=${D_CONTAINER_NAME} \
        --env SCENARIO=`echo ${CURRENT_SCENARIO}` \
        --env RESULT_FILE=`echo ${D_RESULT_FILE}` \
        --env STAGE=`echo $1` \
        --env TZ=`echo ${TIMEZONE}` \
        --volume ${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/database.xml:/xml/${CURRENT_SCENARIO}.xml \
        --volume ${DIR_PREFIX}/tmp/output:/output \
        ${D_IMAGE}

    docker rm ${R_CONTAINER_NAME} >> /dev/null 2>&1
}

# Script controlled variables
DIR_PREFIX=`pwd`
# First arument - single test to run
SCENARIO="$1"

if [ "x${SCENARIO}" != "x" ]; then
    SCENARIO=`basename ${SCENARIO} | cut -f 1 -d .`
fi

# prepare
P_IMAGE=volts_prepare:latest
P_CONTAINER_NAME=volts_prepare

mkdir -p tmp/input
mkdir -p tmp/output
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
VP_LOG_LEVEL_FILE=${VP_LOG_LEVEL}

rm -f ${DIR_PREFIX}/tmp/output/${D_RESULT_FILE}
rm -f ${DIR_PREFIX}/tmp/output/${VP_RESULT_FILE}

if [ -z ${SCENARIO} ]; then
    for D in ${DIR_PREFIX}/tmp/input/*; do
        if [ -f ${D}/voip_patrol.xml ]; then
            CURRENT_SCENARIO=`basename ${D}`
            run_database pre
            run_voip_patrol
            run_database post
        fi
    done
else
    CURRENT_SCENARIO=${SCENARIO}
    run_database pre
    run_voip_patrol
    run_database post
fi

# report
R_IMAGE=volts_report:latest
R_CONTAINER_NAME=volts_report

run_report

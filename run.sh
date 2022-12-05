#!/bin/bash
# Main user controlled variables
# Report type to provide
REPORT_TYPE='table_full'
# Log level on console
LOG_LEVEL=0
# Timezone
TIMEZONE=`timedatectl show --property=Timezone --value`


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
    --env LOG_LEVEL=`echo ${LOG_LEVEL}` \
    --env LOG_LEVEL_FILE=`echo ${LOG_LEVEL_FILE}` \
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
        --env M_RESULT_FILE=`echo ${M_RESULT_FILE}` \
        --env SIPP_RESULT_FILE=`echo ${SIPP_RESULT_FILE}` \
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

    docker rm ${D_CONTAINER_NAME} >> /dev/null 2>&1
}

run_sipp() {
    docker rm ${SIPP_CONTAINER_NAME} >> /dev/null 2>&1

    if [ ! -f "${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/sipp.xml" ]; then
        return
    fi

    docker run --name=${SIPP_CONTAINER_NAME} \
        --env SCENARIO=`echo ${CURRENT_SCENARIO}` \
        --env RESULT_FILE=`echo ${SIPP_RESULT_FILE}` \
        --env LOG_LEVEL=`echo ${LOG_LEVEL}` \
        --volume ${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/sipp.xml:/xml/${CURRENT_SCENARIO}.xml \
        --volume ${DIR_PREFIX}/tmp/output:/output \
        ${SIPP_IMAGE}

    docker rm ${SIPP_CONTAINER_NAME} >> /dev/null 2>&1
}

run_media() {
    docker rm ${M_CONTAINER_NAME} >> /dev/null 2>&1

    if [ ! -f "${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/media_check.xml" ]; then
        return
    fi

    docker run --name=${M_CONTAINER_NAME} \
        --env SCENARIO=`echo ${CURRENT_SCENARIO}` \
        --env RESULT_FILE=`echo ${M_RESULT_FILE}` \
        --volume ${DIR_PREFIX}/tmp/input/${CURRENT_SCENARIO}/media_check.xml:/xml/${CURRENT_SCENARIO}.xml \
        --volume ${DIR_PREFIX}/tmp/output:/output \
        ${M_IMAGE}

    docker rm ${M_CONTAINER_NAME} >> /dev/null 2>&1
}


# Script controlled variables
DIR_PREFIX=`pwd`
# First arument - single test to run
SCENARIO="$1"

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

rm -f ${DIR_PREFIX}/tmp/output/${D_RESULT_FILE}
rm -f ${DIR_PREFIX}/tmp/output/${M_RESULT_FILE}
rm -f ${DIR_PREFIX}/tmp/output/${VP_RESULT_FILE}
rm -f ${DIR_PREFIX}/tmp/output/${SIPP_RESULT_FILE}

if [ -z ${SCENARIO} ]; then
    for D in ${DIR_PREFIX}/tmp/input/*; do
        CURRENT_SCENARIO=`basename ${D}`
        run_database pre
        run_voip_patrol
        run_sipp
        run_database post
        run_media
    done
else
    CURRENT_SCENARIO=${SCENARIO}
    run_database pre
    run_voip_patrol
    run_sipp
    run_database post
    run_media
fi

# report
R_IMAGE=volts_report:latest
R_CONTAINER_NAME=volts_report

run_report

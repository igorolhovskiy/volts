#!/bin/sh

if [ "$1" = "-r" ]; then
    docker image rm volts_vp:latest >> /dev/null 2>&1
    docker image rm volts_sipp:latest >> /dev/null 2>&1
    docker image rm volts_opensips:latest >> /dev/null 2>&1
    BUILD_OPT_CACHE="--no-cache"
fi

docker build --file build/Dockerfile.prepare --platform linux/amd64 --tag volts_prepare build/
docker build $BUILD_OPT_CACHE --file build/Dockerfile.vp --platform linux/amd64 --tag volts_vp build/
docker build --file build/Dockerfile.report --platform linux/amd64 --tag volts_report build/
docker build --file build/Dockerfile.database --platform linux/amd64 --tag volts_database build/
docker build --file build/Dockerfile.media --platform linux/amd64 --tag volts_media build/
docker build $BUILD_OPT_CACHE --file build/Dockerfile.sipp --platform linux/amd64 --tag volts_sipp build/
docker build $BUILD_OPT_CACHE --file build/Dockerfile.opensips --platform linux/amd64 --tag volts_opensips build/

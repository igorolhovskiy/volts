#!/bin/sh

if [ "$1" = "-r" ]; then
    docker image rm volts_vp:latest
fi

docker build --file build/Dockerfile.prepare --tag volts_prepare build/
docker build --file build/Dockerfile.vp --tag volts_vp build/
docker build --file build/Dockerfile.report --tag volts_report build/
docker build --file build/Dockerfile.database --tag volts_database build/

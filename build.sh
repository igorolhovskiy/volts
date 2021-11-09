#!/bin/sh
docker build --file build/Dockerfile.prepare --tag volts_prepare build/
docker build --file build/Dockerfile.vp --tag volts_vp build/
docker build --file build/Dockerfile.report --tag volts_report build/

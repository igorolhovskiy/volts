#!/bin/bash

# Cleanup old data
rm -rf /opt/output/*
# Prepare new data
python3 /root/database.py
# Make sure data is accessible
chmod -R 777 /opt/

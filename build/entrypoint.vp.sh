#!/bin/bash

RESULT_FILE=${RESULT_FILE-"result.json"}
PORT=${PORT="5060"}

echo " >--- Running scenario ${XML_CONF}"

/git/voip_patrol/voip_patrol --port ${PORT} --conf /xml/${XML_CONF}.xml --output /output/${RESULT_FILE} --log-level-file ${LOG_LEVEL_FILE} --log-level-console ${LOG_LEVEL}

echo " ---> Scenario ${XML_CONF} done"

chmod 777 /output
chmod 666 /output/${RESULT_FILE}

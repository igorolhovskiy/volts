#!/bin/bash

# Start OpenSIPS with m4 processed template. Move to Jinja?

echo "
divert(-1)
define(\`TLS_PORT', \`${OPENSIPS_TLS_PORT}')
define(\`WSS_PORT', \`${OPENSIPS_WSS_PORT}')
define(\`HEPS_PORT', \`${OPENSIPS_HEPS_PORT}')
define(\`HEPD_PORT', \`${OPENSIPS_HEPD_PORT}')
define(\`VP_TLS_PORT', \`${VP_TLS_PORT}')
divert(0)dnl
" > /etc/opensips/defines.m4

/usr/bin/m4 /etc/opensips/defines.m4 /etc/opensips/opensips.cfg.m4 > /etc/opensips/opensips.cfg

/usr/sbin/opensips -D

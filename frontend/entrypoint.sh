#!/bin/sh
# Substitute environment variables in env-config.js
envsubst '${API_URL}' < /usr/share/nginx/html/env-config.js.template > /usr/share/nginx/html/env-config.js
exec nginx -g "daemon off;"

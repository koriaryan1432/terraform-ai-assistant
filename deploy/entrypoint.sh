#!/bin/bash
# Start backend in the background with gunicorn
gunicorn -w 2 -k uvicorn.workers.UvicornWorker app:app \
    --bind 0.0.0.0:8001 \
    --access-logfile - \
    --error-logfile - &
BACKEND_PID=$!

# Wait for backend to be ready
for i in $(seq 1 30); do
    if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Start nginx in foreground
nginx -g "daemon off;" &
NGINX_PID=$!

# Wait for either process to exit
wait -n $BACKEND_PID $NGINX_PID
exit 1

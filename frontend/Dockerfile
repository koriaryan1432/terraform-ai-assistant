# Use nginx Alpine for minimal footprint
FROM nginx:alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/

# Copy frontend files
COPY . /usr/share/nginx/html/

# Install envsubst (comes with gettext-base)
RUN apk add --no-cache gettext

# Copy env config template and entrypoint
COPY env-config.js /usr/share/nginx/html/env-config.js.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set permissions (optional for nginx)
RUN chmod -R 755 /usr/share/nginx/html

# Environment variable (set at runtime via docker or render)
ENV API_URL=http://localhost:8001

# Expose port
EXPOSE 80

# Use entrypoint script for runtime env var substitution
ENTRYPOINT ["/entrypoint.sh"]

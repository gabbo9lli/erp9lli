# Use a lightweight, stable Nginx base image
FROM nginx:stable-alpine

# Copy the custom configuration file into the default Nginx configuration directory
# This replaces the default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose the port Nginx is listening on
EXPOSE 80

# Command to run Nginx (default is fine)
CMD ["nginx", "-g", "daemon off;"]
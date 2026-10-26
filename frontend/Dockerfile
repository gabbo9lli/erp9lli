# syntax=docker/dockerfile:1
FROM node:20-alpine AS base

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# Development Stage
FROM base AS development
ENV NODE_ENV=development
# Expose the Vite/Vue CLI port
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

# Build Stage (Temporary)
FROM base AS build-stage
RUN npm run build

# Production Stage: Nginx serving the Vue SPA bundle on port 80
FROM nginx:alpine AS production
WORKDIR /usr/share/nginx/html
COPY --from=build-stage /app/dist /usr/share/nginx/html

RUN printf 'server {\n    listen 80;\n    location / {\n        root /usr/share/nginx/html;\n        index index.html;\n        try_files $uri $uri/ /index.html;\n    }\n}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

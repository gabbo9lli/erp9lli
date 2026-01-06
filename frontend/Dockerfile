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

# Production Stage
FROM nginx:stable-alpine AS production
# Copy the compiled files from build-stage to Nginx
COPY --from=build-stage /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
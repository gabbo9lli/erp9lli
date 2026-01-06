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
FROM alpine:latest AS production
WORKDIR /app

# Copy files from build-stage to the directory mapped in your compose volume
COPY --from=build-stage /app/dist /app/dist

RUN ls -la /app/dist
# This container doesn't need to run a server, 
# it just needs to exist so the volume is populated.
CMD ["sleep", "infinity"]
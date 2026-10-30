# syntax=docker/dockerfile:1

# ---- Stage build: Vue + Vite ----
FROM node:22-alpine AS build
WORKDIR /app

# Chép manifest trước để tận dụng cache layer của npm ci
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
ENV VITE_USE_MOCK=false
RUN npm run build

# ---- Stage chạy: nginx ----
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

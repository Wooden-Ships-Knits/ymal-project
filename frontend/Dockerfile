# Two stages: build the SPA with node, serve it with nginx. The node toolchain
# never reaches the running container — same shape as wholesale-order-entry.

# ---- stage 1: build
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---- stage 2: serve
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

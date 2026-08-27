# ---------- Build stage ----------
FROM node:20-alpine AS builder

# Backend base URL baked into the bundle (host only, no /api/v1 suffix)
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---------- Serve stage ----------
FROM nginx:1.27-alpine AS runtime

# SPA routing: serve index.html for unknown paths
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

# Run nginx as the unprivileged bundled user on an unprivileged port
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/ > /dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]

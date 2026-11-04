# The Rihla web app (rihla-frontend/), built once and served by nginx, which also forwards /api to the backend so
# the page and the API share one origin (as the Vite dev proxy does). Build context: kit/ (see docker-compose.yml).

# ---- build: the same commands as on a laptop (npm ci + vite build)
FROM node:22-slim AS build
WORKDIR /web
COPY rihla-frontend/package.json rihla-frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY rihla-frontend/ ./

# Vite writes VITE_* values into the bundle at build time. They are build arguments, not files: no .env file is
# copied (see .dockerignore). The Firebase web values identify the project and are public by design; the backend
# verifies every sign-in itself (app/auth/INTEGRATION.md). Never pass a server secret here.
ARG VITE_ENABLE_LIVE_AI=true
ARG VITE_FIREBASE_API_KEY=
ARG VITE_FIREBASE_AUTH_DOMAIN=
ARG VITE_FIREBASE_PROJECT_ID=
ARG VITE_FIREBASE_APP_ID=
ENV VITE_ENABLE_LIVE_AI=$VITE_ENABLE_LIVE_AI \
    VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY \
    VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN \
    VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID \
    VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID
RUN npm run build

# ---- serve: static files + the /api proxy
FROM nginx:1.27-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

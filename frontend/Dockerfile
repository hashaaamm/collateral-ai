# syntax=docker/dockerfile:1
# React + Vite SPA → static build, served by `vite preview` (or swap for Caddy) on 8080.

FROM node:24-slim AS build
WORKDIR /app
RUN corepack enable
ARG VITE_API_URL
ARG VITE_SITE_URL
ENV VITE_API_URL=$VITE_API_URL VITE_SITE_URL=$VITE_SITE_URL
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install
COPY . .
RUN pnpm build

FROM node:24-slim AS runner
WORKDIR /app
RUN corepack enable && addgroup --system app && adduser --system --ingroup app app
COPY --from=build --chown=app:app /app/dist ./dist
COPY --from=build --chown=app:app /app/package.json ./package.json
COPY --from=build --chown=app:app /app/node_modules ./node_modules
USER app
ENV PORT=8080
EXPOSE 8080
# vite preview serves the SPA with index.html fallback. For higher throughput, replace with Caddy.
CMD ["sh", "-c", "pnpm preview --host --port ${PORT:-8080}"]

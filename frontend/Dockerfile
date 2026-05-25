# syntax=docker/dockerfile:1.7
FROM node:22-trixie-slim AS builder
WORKDIR /app
RUN corepack enable
COPY pnpm-lock.yaml package.json .npmrc pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
ENV CI=true
RUN pnpm build

FROM node:22-trixie-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
COPY --from=builder /app/package.json /app/pnpm-lock.yaml /app/.npmrc ./
RUN corepack enable && pnpm install --frozen-lockfile --prod
COPY --from=builder /app/build ./build
EXPOSE 3000
CMD ["node", "build"]

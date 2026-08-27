# syntax=docker/dockerfile:1.7

FROM node:24-trixie-slim AS builder
WORKDIR /app
RUN corepack enable
COPY pnpm-lock.yaml package.json .npmrc pnpm-workspace.yaml ./
RUN --mount=type=cache,id=oecophylla-pnpm-store,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile
COPY . .
ENV CI=true
RUN pnpm build

FROM node:24-trixie-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
# package.json contains only devDependencies and the generated adapter-node
# output is self-contained, so the runtime needs no pnpm or node_modules layer.
COPY --from=builder --chown=node:node /app/build ./build
USER node
EXPOSE 3000
CMD ["node", "build"]

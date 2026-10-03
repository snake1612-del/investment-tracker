FROM node:24-slim
RUN npm install --global pnpm@11.25.0

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --fetch-timeout=300000
COPY . .

EXPOSE 3000
# Re-sync the isolated dependency volume when a rebuilt image/lockfile changes.
# Webpack polling supports Windows bind mounts without additional dev tooling.
CMD ["sh", "-c", "pnpm install --frozen-lockfile && exec pnpm dev --hostname 0.0.0.0 --port 3000 --webpack"]

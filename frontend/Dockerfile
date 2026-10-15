# GeoSketch frontend (Vite + React dev server) - optional, see ../docker-compose.yml
FROM node:22-alpine

WORKDIR /app

# Install dependencies from the lockfile first for a cache-friendly build.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# --host 0.0.0.0 makes the dashboard reachable outside the container
# (e.g. from a phone on the same Wi-Fi during a demo).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

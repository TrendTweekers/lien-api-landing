# Stage 1: Build React Dashboard
FROM node:20-alpine AS build

WORKDIR /app

# Copy package files and install dependencies
COPY dashboard-v2/deadline-glow-up-main/package*.json dashboard-v2/deadline-glow-up-main/
RUN cd dashboard-v2/deadline-glow-up-main && npm ci

# Copy source code and build
COPY dashboard-v2/deadline-glow-up-main dashboard-v2/deadline-glow-up-main
RUN cd dashboard-v2/deadline-glow-up-main && npm run build

# Verify build output and copy to public/dashboard
RUN ls -la /app/dashboard-v2/deadline-glow-up-main/dist
RUN mkdir -p /app/public/dashboard && cp -r /app/dashboard-v2/deadline-glow-up-main/dist/* /app/public/dashboard/

# Stage 2: Python API
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy app first so any -r ../requirements.txt inside api/requirements.txt works
COPY . /app

# Install Python deps (now /app/requirements.txt exists if referenced)
RUN pip install --no-cache-dir -r /app/api/requirements.txt

# Copy built dashboard from node stage (overwrite with fresh build output)
COPY --from=build /app/public/dashboard /app/public/dashboard

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]


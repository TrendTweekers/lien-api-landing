# Stage 1: Build React Dashboard
FROM node:20-alpine AS build

WORKDIR /app

# Copy package files and install dependencies
COPY dashboard-v2/deadline-glow-up-main/package*.json dashboard-v2/deadline-glow-up-main/
RUN cd dashboard-v2/deadline-glow-up-main && npm ci

# Copy source code and build
COPY dashboard-v2/deadline-glow-up-main dashboard-v2/deadline-glow-up-main
RUN cd dashboard-v2/deadline-glow-up-main && npm run build

# Stage 2: Python API
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt

# Copy application code
COPY . /app

# Copy built dashboard from build stage
COPY --from=build /app/public/dashboard /app/public/dashboard

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]


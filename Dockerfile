FROM node:22-bookworm-slim AS frontend
WORKDIR /build
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN corepack prepare pnpm@11.19.0 --activate && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends chromium chromium-driver fonts-liberation && rm -rf /var/lib/apt/lists/*
ENV CHROME_BIN=/usr/bin/chromium CHROMEDRIVER=/usr/bin/chromedriver CHROME_NO_SANDBOX=true PYTHONUNBUFFERED=1
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements.lock
COPY src/ ./src/
COPY main.py ./
COPY --from=frontend /build/dist ./frontend/dist
EXPOSE 8000
CMD ["uvicorn", "src.web_api:app", "--host", "0.0.0.0", "--port", "8000"]

FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY automation-inspector-frontend/ ./
RUN npm install -g pnpm && pnpm install && pnpm build

FROM python:3.11-alpine
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/app

COPY --from=frontend-builder /frontend/out/ /app/www

EXPOSE 1234
ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "1234"]

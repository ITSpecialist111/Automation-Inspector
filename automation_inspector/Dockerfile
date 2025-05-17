FROM python:3.11-alpine

# Minimal OS packages
RUN apk add --no-cache build-base libffi-dev

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run.sh .
RUN chmod +x /app/run.sh
COPY app/ ./app
COPY www/ ./www

EXPOSE 1234
ENTRYPOINT ["/app/run.sh"]

FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run.sh /app/run.sh
RUN chmod 0755 /app/run.sh

COPY app/ /app/app
COPY www/ /app/www

EXPOSE 1234
ENTRYPOINT ["/app/run.sh"]

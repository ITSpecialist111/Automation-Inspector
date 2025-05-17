# automation_inspector/Dockerfile  (snippet)
FROM python:3.11-alpine
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run.sh /app/run.sh          # copy
RUN chmod 0755 /app/run.sh       # make executable

COPY app/ /app/app
COPY www/ /app/www

ENTRYPOINT ["/app/run.sh"]       # call it directly

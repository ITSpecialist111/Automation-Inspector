FROM python:3.11-alpine

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the launch script *and* make it executable
COPY run.sh /app/run.sh
RUN chmod 0755 /app/run.sh  # <— ensures exec bit

# Copy the rest of the add-on files
COPY app/   /app/app
COPY www/   /app/www

EXPOSE 1234
ENTRYPOINT ["/app/run.sh"]

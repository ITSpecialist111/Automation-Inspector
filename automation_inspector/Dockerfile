FROM python:3.14.6-alpine3.24

ARG BUILD_ARCH=unknown
ARG BUILD_VERSION=dev

LABEL \
	io.hass.type="app" \
	io.hass.arch="${BUILD_ARCH}" \
	io.hass.version="${BUILD_VERSION}" \
	org.opencontainers.image.title="Automation Inspector" \
	org.opencontainers.image.description="Read-only Home Assistant automation health inspector" \
	org.opencontainers.image.source="https://github.com/ITSpecialist111/Automation-Inspector" \
	org.opencontainers.image.licenses="MIT" \
	org.opencontainers.image.version="${BUILD_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_DISABLE_PIP_VERSION_CHECK=1 \
	PIP_NO_CACHE_DIR=1 \
	HOME=/tmp

WORKDIR /opt/automation-inspector

COPY requirements.txt ./requirements.txt
RUN python -m pip install --requirement requirements.txt \
	&& addgroup -S inspector \
	&& adduser -S -D -H -G inspector inspector

COPY --chown=inspector:inspector app/ ./app/
COPY --chown=inspector:inspector www/ ./www/

USER inspector

EXPOSE 1234
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
	CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:1234/health', timeout=3).read()"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "1234", "--proxy-headers", "--forwarded-allow-ips=*", "--no-server-header", "--timeout-keep-alive", "10"]

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    COOKIE_SECURE=true \
    TRUST_PROXY=true \
    PORT=8000

WORKDIR /app
COPY requirements.lock ./
RUN python -m pip install -r requirements.lock \
    && groupadd --system cacau \
    && useradd --system --gid cacau --create-home cacau

COPY --chown=cacau:cacau . .
RUN chmod 755 deploy/entrypoint.sh \
    && mkdir -p /app/instance \
    && chown cacau:cacau /app/instance
USER cacau

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=6s --start-period=150s --retries=3 \
    CMD ["python", "deploy/healthcheck.py"]
ENTRYPOINT ["sh", "/app/deploy/entrypoint.sh"]
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]

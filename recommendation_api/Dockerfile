FROM python:3.13-trixie AS builder
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "${VIRTUAL_ENV}"
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
WORKDIR /app
COPY recommendation_api/requirements.runtime.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.runtime.txt

FROM python:3.13-slim-trixie AS runtime
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin app
COPY --from=builder --chown=10001:10001 /opt/venv /opt/venv
COPY --chown=10001:10001 recommendation_api/app ./app
USER 10001:10001
EXPOSE 8090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]

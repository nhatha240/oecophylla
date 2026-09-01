FROM python:3.13-trixie AS builder
ARG NLP_MODEL_PREFETCH=false
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "${VIRTUAL_ENV}"
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
WORKDIR /app
COPY workers/nlp_worker/requirements.runtime.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.runtime.txt
COPY workers/nlp_worker/app ./app
RUN mkdir -p /opt/models \
    && if [ "${NLP_MODEL_PREFETCH}" = "true" ]; then \
         python -m app.model_download --target /opt/models/multilingual-e5-small; \
       fi

FROM python:3.13-slim-trixie AS runtime
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin app
COPY --from=builder --chown=10001:10001 /opt/venv /opt/venv
COPY --from=builder --chown=10001:10001 /opt/models /opt/models
COPY --chown=10001:10001 workers/nlp_worker/app ./app
USER 10001:10001
CMD ["python", "-m", "app.main"]

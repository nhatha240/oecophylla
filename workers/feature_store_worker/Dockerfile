FROM python:3.13-trixie
WORKDIR /app
COPY workers/feature_store_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY workers/feature_store_worker/app ./app
CMD ["python", "-m", "app.main"]

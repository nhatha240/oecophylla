FROM python:3.13-trixie
WORKDIR /app
COPY workers/nlp_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY workers/nlp_worker/app ./app
CMD ["python", "-m", "app.main"]

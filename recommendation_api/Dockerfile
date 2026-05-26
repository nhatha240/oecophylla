FROM python:3.13-trixie AS runtime
WORKDIR /app
COPY recommendation_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY recommendation_api/app ./app
EXPOSE 8090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]

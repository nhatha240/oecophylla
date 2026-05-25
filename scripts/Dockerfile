FROM python:3.13-trixie
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt
COPY . /app
ENTRYPOINT ["python"]

# One-shot tools image for seeding and offline evaluation.
# Usage (from compose, profile "tools"):
#   docker compose run --rm scripts seed.py
#   docker compose run --rm scripts evaluate.py --k 10
FROM python:3.13-trixie
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# ENTRYPOINT is `python`, so the compose command is just the script + args.
ENTRYPOINT ["python"]
CMD ["seed.py"]

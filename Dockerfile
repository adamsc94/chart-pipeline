FROM python:3.11-slim

WORKDIR /app

# Dependencies first: rarely change, so this layer stays cached
# when only the code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "run_pipeline.py"]
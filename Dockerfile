FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt

COPY pyproject.toml ./
COPY f1reg/ f1reg/
COPY app.py ./
COPY .streamlit/config.toml .streamlit/

COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8501
CMD ["./start.sh"]

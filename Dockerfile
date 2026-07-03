# Dockerfile
FROM python:3.9-slim

# Install uv
RUN pip install uv

WORKDIR /app

# Copy dependency files and install
COPY pyproject.toml .
RUN uv sync --no-dev

# Copy source
COPY . .

CMD ["uv", "run", "python", "main.py"]

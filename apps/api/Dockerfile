FROM python:3.12-slim

# Install uv
RUN pip install uv

WORKDIR /app

# Install dependencies using uv workspace
COPY pyproject.toml .
COPY packages/core ./packages/core
COPY packages/adapters ./packages/adapters
COPY apps/api ./apps/api
COPY apps/web ./apps/web
COPY data ./data

RUN uv pip install --system -e packages/core -e packages/adapters -e apps/api click rich

EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

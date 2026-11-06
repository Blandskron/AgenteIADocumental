FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m pip install --no-cache-dir pip==26.3

COPY app ./app

FROM base AS test
COPY requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt
COPY tests ./tests
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]

FROM base AS audit
RUN python -m pip freeze --all > /tmp/runtime-packages.txt
RUN python -m pip install --no-cache-dir pip-audit==2.10.1
CMD ["pip-audit", "--disable-pip", "--no-deps", "--cache-dir", "/tmp/pip-audit-cache", "-r", "/tmp/runtime-packages.txt"]

FROM base AS runtime
EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

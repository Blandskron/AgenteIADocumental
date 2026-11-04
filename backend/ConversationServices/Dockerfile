FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd --gid 10002 conversation \
    && useradd --uid 10002 --gid conversation --no-create-home conversation

COPY app ./app

FROM base AS test

COPY requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt
COPY tests ./tests
USER 10002:10002
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]

FROM base AS runtime

USER 10002:10002
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

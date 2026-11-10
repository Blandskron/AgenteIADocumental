FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m pip install --no-cache-dir pip==26.3

COPY app ./app

FROM base AS audit
RUN python -m pip freeze --all > /tmp/runtime-packages.txt
RUN python -m pip install --no-cache-dir pip-audit==2.10.1
USER 10006:10006
CMD ["pip-audit", "--disable-pip", "--no-deps", "--cache-dir", "/tmp/pip-audit-cache", "-r", "/tmp/runtime-packages.txt"]

FROM base AS test

COPY requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt
COPY tests ./tests
USER 10006:10006
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]

FROM base AS runtime

RUN python -m pip check && python -m pip uninstall -y pip && rm -rf /usr/local/lib/python3.12/ensurepip
USER 10006:10006

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

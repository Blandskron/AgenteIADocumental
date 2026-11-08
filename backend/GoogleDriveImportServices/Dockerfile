FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS base
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip check
COPY app ./app

FROM base AS test
COPY requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt
COPY tests ./tests
COPY pytest.ini .
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]

FROM base AS audit
RUN pip freeze --all --exclude pip > /tmp/runtime-packages.txt
RUN pip install --no-cache-dir pip-audit==2.10.1
CMD ["pip-audit", "--disable-pip", "--no-deps", "--cache-dir", "/tmp/pip-audit-cache", "-r", "/tmp/runtime-packages.txt"]

FROM base AS runtime
RUN python -m pip uninstall -y pip
USER 10010:10010
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

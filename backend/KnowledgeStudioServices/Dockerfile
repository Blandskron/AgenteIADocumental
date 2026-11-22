FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pip==26.3 setuptools==84.2.1

RUN groupadd --gid 10018 studio \
    && useradd --uid 10018 --gid studio --create-home studio

COPY app ./app

FROM base AS runtime
RUN python -m pip check && python -m pip uninstall -y pip && rm -rf /usr/local/lib/python3.12/ensurepip
USER 10018:10018
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


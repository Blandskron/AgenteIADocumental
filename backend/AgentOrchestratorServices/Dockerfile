FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m pip uninstall -y pip setuptools wheel || true \
    && rm -rf /usr/local/lib/python3.12/ensurepip

COPY app ./app

RUN groupadd -g 10019 agent && useradd -u 10019 -g 10019 -m -s /usr/sbin/nologin agent \
    && chown -R 10019:10019 /app

USER 10019:10019
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

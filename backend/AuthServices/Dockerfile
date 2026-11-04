FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_PRIVATE_KEY_PATH=/app/signing_keys/private.pem
ENV DJANGO_PUBLIC_KEY_PATH=/app/verification_keys/public.pem

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 auth \
    && useradd --uid 10001 --gid auth --no-create-home auth \
    && install -d -o auth -g auth /app/signing_keys /app/verification_keys

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./
RUN sed -i 's/\r$//' /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh \
    && key_dir="$(mktemp -d)" \
    && DJANGO_PRIVATE_KEY_PATH="$key_dir/private.pem" DJANGO_PUBLIC_KEY_PATH="$key_dir/public.pem" \
       python manage.py collectstatic --noinput \
    && rm -r "$key_dir"

EXPOSE 8001

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8001", "--workers", "2", "--timeout", "60"]

FROM node:24-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03

USER root
RUN sed -i 's/^\(nginx[^=]*\)=.*/\1/' /etc/apk/world \
    && apk upgrade --no-cache -X "https://nginx.org/packages/alpine/v$(egrep -o '^[0-9]+\.[0-9]+' /etc/alpine-release)/main"

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker-entrypoint.d/20-runtime-config.sh /docker-entrypoint.d/20-runtime-config.sh
RUN sed -i 's/\r$//' /docker-entrypoint.d/20-runtime-config.sh \
    && chmod +x /docker-entrypoint.d/20-runtime-config.sh

USER 101:101

EXPOSE 8080

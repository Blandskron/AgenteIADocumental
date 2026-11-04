FROM node:24-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . ./
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker-entrypoint.d/20-runtime-config.sh /docker-entrypoint.d/20-runtime-config.sh
RUN sed -i 's/\r$//' /docker-entrypoint.d/20-runtime-config.sh \
    && chmod +x /docker-entrypoint.d/20-runtime-config.sh

EXPOSE 80

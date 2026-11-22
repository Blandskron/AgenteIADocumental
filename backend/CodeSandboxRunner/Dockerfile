FROM denoland/deno:alpine-2.2.12

WORKDIR /app

COPY server.ts ./server.ts

RUN addgroup -g 10020 -S sandbox && adduser -u 10020 -S -G sandbox sandbox \
    && chown -R 10020:10020 /app

USER 10020:10020
EXPOSE 8090

# The HTTP coordinator only binds to internal container port 8090 and spawns each user script
# in an isolated child process with `deno run --deny-all --no-remote --no-npm` and clearEnv=true.
CMD ["deno", "run", "--allow-net=0.0.0.0:8090", "--allow-run=deno", "--allow-write=/tmp", "--allow-read=/tmp,/app", "server.ts"]

FROM golang:1.27-alpine@sha256:70bd7ddea8b6cbe5d6943cde279d6b67feb10cc924fb9100d1d8757c1575b280 AS gosu-build

ADD --checksum=sha256:207a2045e890d3ca3326027c5f585733085960b401a49dbc00e3bb628c054cf8 \
    https://codeload.github.com/tianon/gosu/tar.gz/refs/tags/1.20 /tmp/gosu.tar.gz
WORKDIR /src
RUN tar -xzf /tmp/gosu.tar.gz --strip-components=1 \
    && CGO_ENABLED=0 GOTOOLCHAIN=local go build -trimpath -mod=readonly -ldflags='-s -w' -o /out/gosu . \
    && cp LICENSE /out/gosu-LICENSE

FROM postgres:16.16-alpine3.24@sha256:1d5b02d3a9941fbd52437db4107f8c52d6297dac553ca1e5c299ebb3756b4857 AS postgres-base

RUN apk upgrade --no-cache

FROM postgres-base AS vector-build

RUN apk add --no-cache build-base
ADD --checksum=sha256:cac0b10c360f05b2d521200105ba3697e773d4cd3731f5a915a7e37ebe0bea85 \
    https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v0.8.7 /tmp/pgvector.tar.gz
WORKDIR /src
RUN tar -xzf /tmp/pgvector.tar.gz --strip-components=1 \
    && make OPTFLAGS="" with_llvm=no -j "$(getconf _NPROCESSORS_ONLN)" \
    && make OPTFLAGS="" with_llvm=no install DESTDIR=/out \
    && cp LICENSE /out/pgvector-LICENSE

FROM postgres-base AS runtime

COPY --from=gosu-build /out/gosu /usr/local/bin/gosu
COPY --from=gosu-build /out/gosu-LICENSE /usr/local/share/licenses/gosu/LICENSE
COPY --from=vector-build /out/usr/local/ /usr/local/
COPY --from=vector-build /out/pgvector-LICENSE /usr/local/share/licenses/pgvector/LICENSE
COPY --chmod=0755 entrypoint.sh /usr/local/bin/blandskron-postgres

ENV PGDATA=/var/lib/postgresql/data/pgdata
ENTRYPOINT ["blandskron-postgres"]
CMD ["postgres"]

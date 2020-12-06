##############################################################################################################
FROM rust:1.48.0-alpine3.12 as builder
WORKDIR /proxy
COPY . /proxy
RUN apk add --no-cache musl-dev g++ && cargo build --release

##############################################################################################################
FROM alpine:3.12 as clickhouse-proxy
WORKDIR /proxy
COPY --from=builder /proxy/target/release/clickhouse-proxy /proxy
CMD /proxy/clickhouse-proxy
ARG kkver=0.0
LABEL kkver=${kkver} kkname=clickhouse-proxy

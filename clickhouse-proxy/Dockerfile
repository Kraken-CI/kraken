##############################################################################################################
FROM krakenci/chp-builder:20221108 as builder

# copy your source tree
COPY ./src ./src
COPY ./Cargo.lock ./Cargo.lock
COPY ./Cargo.toml ./Cargo.toml

# build for release
RUN rm ./target/release/deps/clickhouse_proxy*
ARG kkver=0.0
RUN KRAKEN_VERSION=${kkver} cargo build --release

##############################################################################################################
FROM debian:bullseye-20231218-slim as clickhouse-proxy
WORKDIR /proxy
COPY --from=builder /proxy/target/release/clickhouse-proxy /proxy
CMD /proxy/clickhouse-proxy
ARG kkver=0.0
LABEL kkver=${kkver} kkname=clickhouse-proxy

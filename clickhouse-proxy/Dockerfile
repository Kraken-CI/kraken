##############################################################################################################
FROM krakenci/chp-builder as builder

# copy your source tree
COPY ./src ./src
COPY ./Cargo.lock ./Cargo.lock
COPY ./Cargo.toml ./Cargo.toml

# build for release
RUN rm ./target/release/deps/clickhouse_proxy*
RUN cargo build --release

##############################################################################################################
FROM alpine:3.14 as clickhouse-proxy
WORKDIR /proxy
COPY --from=builder /proxy/target/release/clickhouse-proxy /proxy
CMD /proxy/clickhouse-proxy
ARG kkver=0.0
LABEL kkver=${kkver} kkname=clickhouse-proxy

FROM nginx:1@sha256:b997b0db9c2bc0a2fb803ced5fb9ff3a757e54903a28ada3e50412cc3ab7822f

RUN apt-get update && apt-get install -y "wait-for-it" && rm -rf /var/lib/apt/lists/*

COPY dist/kraken /usr/share/nginx/html
COPY nginx.conf /tmp/nginx.conf.tpl

EXPOSE 80

CMD wait-for-it -t 0 ${KRAKEN_SERVER_ADDR} -- /bin/bash -c "DOLLAR=\$ envsubst < /tmp/nginx.conf.tpl > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"

FROM nginx

COPY dist/kraken /usr/share/nginx/html
COPY nginx.conf /tmp/nginx.conf.tpl

RUN apt-get update && apt-get install -y "wait-for-it"

EXPOSE 80

CMD wait-for-it -t 0 ${KRAKEN_SERVER_ADDR} -- /bin/bash -c "DOLLAR=\$ envsubst < /tmp/nginx.conf.tpl > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"

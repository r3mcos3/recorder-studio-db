ARG BUILD_FROM=ghcr.io/home-assistant/base:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-aiohttp py3-yaml py3-psycopg2 py3-pymysql su-exec \
    postgresql postgresql-client mariadb mariadb-client

# Alpine ships MariaDB with skip-networking; Home Assistant must reach it over TCP.
RUN sed -i "s/^[[:space:]]*skip-networking.*/# skip-networking disabled by Recorder Studio DB/" /etc/my.cnf.d/*.cnf

COPY app /app
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]

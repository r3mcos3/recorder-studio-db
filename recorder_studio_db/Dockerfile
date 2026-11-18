ARG BUILD_FROM=ghcr.io/home-assistant/base:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-aiohttp py3-yaml py3-psycopg2 py3-pymysql su-exec \
    postgresql postgresql-client mariadb mariadb-client

# Alpine ships MariaDB with skip-networking; Home Assistant must reach it over TCP.
RUN sed -i "s/^[[:space:]]*skip-networking.*/# skip-networking disabled by Recorder Studio DB/" /etc/my.cnf.d/*.cnf

COPY app /app
COPY rootfs /
COPY run.sh /run.sh
RUN chmod a+x /run.sh /usr/local/bin/prestop /etc/services.d/prestop/run

# On a container stop s6 waits this long (ms) for its services; the prestop service needs it to stop the database gracefully.
ENV S6_SERVICES_GRACETIME=9000

CMD ["/run.sh"]

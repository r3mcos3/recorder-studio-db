# Pinned to a dated base image so Renovate can propose updates (30 days after release, same Alpine version only).
ARG BUILD_FROM=ghcr.io/home-assistant/base:3.24-2026.11.1
FROM ${BUILD_FROM}

# Database major versions are pinned on purpose: a new major needs a data migration, so it is never picked up by accident.
# Minor/patch releases of both arrive with each add-on rebuild.
RUN apk add --no-cache python3 py3-aiohttp py3-yaml py3-psycopg2 py3-pymysql su-exec \
    postgresql18 postgresql18-client "mariadb~=11.8" "mariadb-client~=11.8"

# Alpine ships MariaDB with skip-networking; Home Assistant must reach it over TCP.
RUN sed -i "s/^[[:space:]]*skip-networking.*/# skip-networking disabled by Recorder Studio DB/" /etc/my.cnf.d/*.cnf

COPY app /app
COPY rootfs /
COPY run.sh /run.sh
RUN chmod a+x /run.sh /usr/local/bin/prestop /etc/services.d/prestop/run

# On a container stop s6 waits this long (ms) for its services; the prestop service needs it to stop the database gracefully.
ENV S6_SERVICES_GRACETIME=9000

CMD ["/run.sh"]

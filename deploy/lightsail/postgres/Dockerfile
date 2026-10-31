# PostgreSQL 18 runtime plus owner-approved pgBackRest 2.60.0.
# The package is installed from the signed PGDG Bookworm repository inherited
# from the official PostgreSQL image and pinned to its verified package version.
# PostgreSQL 18 changed PGDATA to /var/lib/postgresql/18/docker.
FROM postgres:18.6-bookworm@sha256:bbf83594798e144bff365a9c191c5d779f181fb3135902064ab8ff11918020fc

ARG PGBACKREST_VERSION=2.60.0-1.pgdg12+1
RUN apt-get update \
    && apt-get install -y --no-install-recommends "pgbackrest=${PGBACKREST_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

COPY pgbackrest.conf /etc/pgbackrest/pgbackrest.conf
COPY entrypoint.sh /usr/local/bin/ubyhost-postgres-entrypoint
COPY pgbackrest-runner.sh /usr/local/bin/pgbackrest-runner
RUN chmod 0555 /usr/local/bin/ubyhost-postgres-entrypoint /usr/local/bin/pgbackrest-runner \
    && chown root:root /etc/pgbackrest/pgbackrest.conf \
    && chmod 0444 /etc/pgbackrest/pgbackrest.conf

ENTRYPOINT ["/usr/local/bin/ubyhost-postgres-entrypoint"]
CMD ["postgres"]

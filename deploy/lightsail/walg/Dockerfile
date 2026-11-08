# 1009: image for the walg sidecar only (compose profile "walg"). The production
# postgres service keeps its pinned Alpine image and never runs wal-g. Debian
# (glibc) because the WAL-G release binaries are built for glibc. The Postgres 16
# binaries here are used only by the restore drill (docs/OPERATIONS.md).
FROM postgres:16.15-bookworm@sha256:5264710be20f409750ac6dc4e5706dcef929c87e241605463f0f9aefa932a8d9
ARG WALG_VERSION=v3.0.9
ARG WALG_ASSET=wal-g-pg-22.04-amd64.tar.gz
ARG WALG_SHA256=4f03ee4679db7f660bfd1b2b8291ac5df247cd2ec48074b60c112f4897299f24
RUN set -eu \
 && apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL -o /tmp/walg.tar.gz "https://github.com/wal-g/wal-g/releases/download/${WALG_VERSION}/${WALG_ASSET}" \
 && echo "${WALG_SHA256}  /tmp/walg.tar.gz" | sha256sum -c - \
 && mkdir /tmp/walg \
 && tar -xzf /tmp/walg.tar.gz -C /tmp/walg \
 && install -m 0755 "$(find /tmp/walg -type f | head -1)" /usr/local/bin/wal-g \
 && rm -rf /tmp/walg /tmp/walg.tar.gz \
 && wal-g --version
COPY walg-ship.sh /usr/local/bin/walg-ship.sh
RUN chmod 0755 /usr/local/bin/walg-ship.sh

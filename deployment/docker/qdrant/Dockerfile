FROM qdrant/qdrant:v1.14.1

USER root
RUN apt-get update \
    && apt-get install --no-install-recommends --yes curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 qdrant \
    && useradd --system --uid 10001 --gid qdrant --home-dir /qdrant --no-create-home qdrant \
    && chown -R qdrant:qdrant /qdrant

USER qdrant

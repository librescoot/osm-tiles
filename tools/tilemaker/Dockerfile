# Tilemaker build pinned to the thread-scheduling-independent output commits.
#
# Upstream tilemaker orders attributes, features and parent relations by
# insertion order, which follows thread scheduling. Two builds of the same PBF
# therefore differ in roughly half of their tiles, and every monthly rebuild
# changes tiles that the OSM data did not change. PR 981 replaces those keys
# with content-based ones; on a Bremen extract the share of tiles that differ
# between two runs of the same input drops from 52% to 0.
#
# Build with:
#   docker build -t tilemaker-deterministic tools/tilemaker
#
# The base image digest and the tilemaker commit are pinned so a rebuild is
# reproducible. Update both together with the patch set below when upstream
# merges the change and a new release is chosen.
ARG DEBIAN_IMAGE=debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2

FROM ${DEBIAN_IMAGE} AS build

ARG TILEMAKER_COMMIT=0bf498b6208c1205bc1e87585638d0a19d23d9ea

# Boost is pinned on both stages: the runtime stage installs shared libraries by
# version, so a distro-side default bump would otherwise produce an image whose
# binary cannot load.

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        git \
        libboost-filesystem1.83-dev \
        libboost-program-options1.83-dev \
        libboost-system1.83-dev \
        liblua5.1-0-dev \
        libshp-dev \
        libsqlite3-dev \
        rapidjson-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN git init -q . \
    && git remote add origin https://github.com/systemed/tilemaker.git \
    && git fetch -q --depth 1 origin "${TILEMAKER_COMMIT}" \
    && git checkout -q FETCH_HEAD \
    && rm -rf .git

RUN cmake -S . -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DTILEMAKER_WITH_MLT=OFF \
    && cmake --build build --target tilemaker --parallel "$(nproc)" \
    && strip build/tilemaker

FROM ${DEBIAN_IMAGE}

LABEL org.opencontainers.image.title="Librescoot tilemaker" \
      org.opencontainers.image.description="Tilemaker with deterministic tile content (upstream PR 981)" \
      org.opencontainers.image.source="https://github.com/librescoot/osm-tiles"

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        libboost-filesystem1.83.0 \
        libboost-program-options1.83.0 \
        liblua5.1-0 \
        libshp4 \
        libsqlite3-0 \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /src/build/tilemaker /usr/local/bin/tilemaker

WORKDIR /data

ENTRYPOINT ["/usr/local/bin/tilemaker"]

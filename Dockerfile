FROM ubuntu:22.04

# Install dependencies for building Tilemaker
RUN apt-get update && apt-get install -y \
    build-essential \
    liblua5.1-0-dev \
    libprotobuf-dev \
    libsqlite3-dev \
    protobuf-compiler \
    shapelib \
    libshp-dev \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-system-dev \
    libboost-iostreams-dev \
    rapidjson-dev \
    git \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Clone and build Tilemaker
WORKDIR /build
RUN git clone https://github.com/systemed/tilemaker.git && \
    cd tilemaker && \
    make && \
    make install

# Set up working directory
WORKDIR /data

# The default command will be specified in the GitHub Actions workflow
# to allow for flexible tile generation
CMD ["/bin/bash"]

# Use official Tilemaker image
FROM ghcr.io/systemed/tilemaker:master

# Set up working directory
WORKDIR /data

CMD ["/bin/bash"]

FROM golang

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .

# The build command is now executed via docker run in the workflow
# to easily get the binary back to the host system.
# The default CMD is removed to allow for this.
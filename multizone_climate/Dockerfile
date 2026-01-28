ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19

# Build stage for Go logic
FROM golang:1.21-alpine AS logic-builder

WORKDIR /build

# Install build dependencies
RUN apk add --no-cache git

# Copy logic source (from addon directory)
COPY ./logic/go.mod ./logic/go.sum ./
RUN go mod download

COPY ./logic/ ./

# Build the Go application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o multizone-logic ./cmd/server

# Final stage
FROM ${BUILD_FROM}

# Install required packages
# Redis for data storage, jq for JSON parsing, bash for scripts, curl for API calls
RUN apk add --no-cache \
    redis \
    jq \
    bash \
    ca-certificates \
    curl

# Copy the Go logic binary from builder
COPY --from=logic-builder /build/multizone-logic /usr/local/bin/

# Copy custom component files (from addon directory)
COPY --chown=root:root ./custom_components /app/custom_components

# Copy s6 service definitions (from addon directory)
COPY --chown=root:root ./rootfs /

# Set working directory
WORKDIR /app

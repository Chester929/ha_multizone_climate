ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install required packages
RUN apk add --no-cache \
    docker-cli \
    docker-compose \
    bash

# Copy custom component files from repository root
COPY --chown=root:root custom_components /app/custom_components

# Copy docker-compose and run script
COPY --chown=root:root hassio-addon/docker-compose.addon.yml /app/docker-compose.yml
COPY --chown=root:root hassio-addon/run /app/run

# Make run script executable
RUN chmod a+x /app/run

# Set working directory
WORKDIR /app

CMD ["/app/run"]

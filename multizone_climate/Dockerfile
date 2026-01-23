ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install required packages
# Note: Docker CLI and docker-compose are required to orchestrate
# the logic and redis containers that make up this addon
RUN apk add --no-cache \
    docker-cli \
    docker-compose \
    jq \
    bash

# Copy custom component files from repository root
COPY --chown=root:root custom_components /app/custom_components

# Copy docker-compose and run script
COPY --chown=root:root multizone_climate/docker-compose.addon.yml /app/docker-compose.yml
COPY --chown=root:root multizone_climate/run /app/run

# Make run script executable
RUN chmod a+x /app/run

# Set working directory
WORKDIR /app

CMD ["/app/run"]

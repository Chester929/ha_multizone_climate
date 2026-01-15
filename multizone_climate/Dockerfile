ARG BUILD_FROM
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install requirements
RUN apk add --no-cache \
    redis \
    python3 \
    py3-pip \
    py3-redis

# Copy run script
COPY run.sh /
RUN chmod a+x /run.sh

# Copy custom integration
COPY custom_components /app/custom_components

# Create data directory for Redis
RUN mkdir -p /data/redis

# Set working directory
WORKDIR /app

# Labels
LABEL \
    io.hass.name="Multizone Climate" \
    io.hass.description="Advanced HVAC zone management with Redis-backed automation" \
    io.hass.type="addon" \
    io.hass.version="1.0.0"

CMD [ "/run.sh" ]

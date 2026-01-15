#!/usr/bin/with-contenv bashio
# ==============================================================================
# Home Assistant Add-on: Multizone Climate
# Starts Redis and manages the multizone climate integration
# ==============================================================================

bashio::log.info "Starting Multizone Climate Add-on..."

# Configuration
REDIS_HOST=$(bashio::config 'redis_host')
REDIS_PORT=$(bashio::config 'redis_port')
REDIS_PASSWORD=$(bashio::config 'redis_password')
REDIS_DB=$(bashio::config 'redis_db')
REDIS_KEY_PREFIX=$(bashio::config 'redis_key_prefix')
INSTALL_INTEGRATION=$(bashio::config 'install_integration')
LOG_LEVEL=$(bashio::config 'log_level')

bashio::log.info "Redis configuration: ${REDIS_HOST}:${REDIS_PORT} (DB: ${REDIS_DB}, Prefix: ${REDIS_KEY_PREFIX})"

# Start Redis server
bashio::log.info "Starting Redis server..."
if bashio::config.has_value 'redis_password'; then
    redis-server \
        --port "${REDIS_PORT}" \
        --requirepass "${REDIS_PASSWORD}" \
        --dir /data/redis \
        --dbfilename dump.rdb \
        --save 900 1 \
        --save 300 10 \
        --save 60 10000 \
        --loglevel "${LOG_LEVEL}" &
else
    redis-server \
        --port "${REDIS_PORT}" \
        --dir /data/redis \
        --dbfilename dump.rdb \
        --save 900 1 \
        --save 300 10 \
        --save 60 10000 \
        --loglevel "${LOG_LEVEL}" &
fi

REDIS_PID=$!
bashio::log.info "Redis started with PID ${REDIS_PID}"

# Wait for Redis to be ready
bashio::log.info "Waiting for Redis to be ready..."
for i in {1..30}; do
    if redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping > /dev/null 2>&1; then
        bashio::log.info "Redis is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        bashio::log.error "Redis failed to start within 30 seconds"
        exit 1
    fi
    sleep 1
done

# Install custom integration if requested
if bashio::var.true "${INSTALL_INTEGRATION}"; then
    bashio::log.info "Installing Multizone Climate custom integration..."
    
    # Create custom_components directory if it doesn't exist
    mkdir -p /config/custom_components
    
    # Copy integration files
    if [ -d /app/custom_components/multizone_climate ]; then
        bashio::log.info "Copying integration files to /config/custom_components/multizone_climate..."
        cp -r /app/custom_components/multizone_climate /config/custom_components/
        bashio::log.info "Integration installed successfully!"
        bashio::log.warning "Please restart Home Assistant to load the integration"
    else
        bashio::log.warning "Integration files not found in /app/custom_components/multizone_climate"
    fi
else
    bashio::log.info "Integration auto-install disabled. Install manually via HACS if needed."
fi

# Keep the add-on running
bashio::log.info "Multizone Climate Add-on is running"
bashio::log.info "Redis is available at ${REDIS_HOST}:${REDIS_PORT}"
bashio::log.info "Configure your climate zones through Home Assistant UI"

# Wait for Redis process
wait ${REDIS_PID}

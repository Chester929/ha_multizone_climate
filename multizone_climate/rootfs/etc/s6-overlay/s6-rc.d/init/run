#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Multizone Climate Add-on initialization..."

# Auto-install custom component
# Try /homeassistant/custom_components first (modern HA standard), fallback to /config/custom_components
if [ -d "/homeassistant" ]; then
    CUSTOM_COMPONENTS_DIR="/homeassistant/custom_components"
elif [ -d "/config" ]; then
    CUSTOM_COMPONENTS_DIR="/config/custom_components"
    bashio::log.info "Using /config path for custom components (legacy mount)"
else
    bashio::log.error "Neither /homeassistant nor /config directory found!"
    exit 1
fi

COMPONENT_NAME="multizone_climate"
COMPONENT_DIR="${CUSTOM_COMPONENTS_DIR}/${COMPONENT_NAME}"
VERSION_FILE="${COMPONENT_DIR}/.installed_version"

# Read version from manifest.json
MANIFEST_PATH="/app/custom_components/${COMPONENT_NAME}/manifest.json"
if [ ! -f "${MANIFEST_PATH}" ]; then
    bashio::log.error "Custom component manifest.json not found at ${MANIFEST_PATH}!"
    exit 1
fi

# Use jq for reliable JSON parsing
ADDON_VERSION=$(jq -r '.version' "${MANIFEST_PATH}")

if [ -z "${ADDON_VERSION}" ] || [ "${ADDON_VERSION}" = "null" ]; then
    bashio::log.error "Could not read version from manifest.json at ${MANIFEST_PATH}"
    exit 1
fi

bashio::log.info "Custom component version: ${ADDON_VERSION}"
bashio::log.info "Target installation directory: ${CUSTOM_COMPONENTS_DIR}"
bashio::log.info "Checking custom component installation..."

# Create custom_components directory if it doesn't exist
if [ ! -d "${CUSTOM_COMPONENTS_DIR}" ]; then
    bashio::log.info "Creating custom_components directory at ${CUSTOM_COMPONENTS_DIR}..."
    mkdir -p "${CUSTOM_COMPONENTS_DIR}" || {
        bashio::log.error "Failed to create directory ${CUSTOM_COMPONENTS_DIR}"
        exit 1
    }
fi

# Function to compare semantic versions
# Returns 0 if version1 > version2, 1 otherwise
version_greater_than() {
    local v1=$1
    local v2=$2
    
    # Split versions into arrays
    IFS='.' read -ra V1 <<< "$v1"
    IFS='.' read -ra V2 <<< "$v2"
    
    # Compare major, minor, patch
    for i in 0 1 2; do
        local num1=${V1[$i]:-0}
        local num2=${V2[$i]:-0}
        
        if [ "$num1" -gt "$num2" ]; then
            return 0
        elif [ "$num1" -lt "$num2" ]; then
            return 1
        fi
    done
    
    # Versions are equal
    return 1
}

# Check if component needs installation/update
INSTALL_NEEDED=false
if [ ! -d "${COMPONENT_DIR}" ]; then
    bashio::log.info "Custom component not found, will install..."
    INSTALL_NEEDED=true
elif [ ! -f "${VERSION_FILE}" ]; then
    bashio::log.info "Version file not found, will reinstall..."
    INSTALL_NEEDED=true
else
    INSTALLED_VERSION=$(cat "${VERSION_FILE}") || {
        bashio::log.warning "Failed to read version file ${VERSION_FILE}, will reinstall"
        INSTALL_NEEDED=true
    }
    
    if [ "${INSTALL_NEEDED}" = false ]; then
        if version_greater_than "${ADDON_VERSION}" "${INSTALLED_VERSION}"; then
            bashio::log.info "Custom component version upgrade available (${INSTALLED_VERSION} -> ${ADDON_VERSION}), will update..."
            INSTALL_NEEDED=true
        elif [ "${INSTALLED_VERSION}" != "${ADDON_VERSION}" ]; then
            bashio::log.warning "Installed version ${INSTALLED_VERSION} is newer than addon version ${ADDON_VERSION}, skipping installation"
        else
            bashio::log.info "Custom component already installed (v${INSTALLED_VERSION})"
        fi
    fi
fi

# Install/update custom component if needed
if [ "${INSTALL_NEEDED}" = true ]; then
    bashio::log.info "Installing custom component v${ADDON_VERSION}..."
    
    # Remove old version if exists
    if [ -d "${COMPONENT_DIR}" ]; then
        rm -rf "${COMPONENT_DIR}" || {
            bashio::log.error "Failed to remove old component directory ${COMPONENT_DIR}"
            exit 1
        }
    fi
    
    # Copy custom component files
    cp -r "/app/custom_components/${COMPONENT_NAME}" "${CUSTOM_COMPONENTS_DIR}/" || {
        bashio::log.error "Failed to copy custom component files to ${CUSTOM_COMPONENTS_DIR}/"
        exit 1
    }
    
    # Write version file
    echo "${ADDON_VERSION}" > "${VERSION_FILE}" || {
        bashio::log.error "Failed to write version file ${VERSION_FILE}"
        exit 1
    }
    
    bashio::log.info "Custom component installed successfully to ${COMPONENT_DIR}!"
    bashio::log.warning "Please restart Home Assistant for the integration to be available"
else
    bashio::log.info "Custom component installation up to date"
fi

bashio::log.info "Multizone Climate Add-on initialization complete"

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
# Returns 0 if version1 > version2, 1 otherwise (1 means equal or less than)
# Note: When comparing different pre-release suffixes (e.g., alpha vs beta) of the same version,
# neither is considered greater as there's no standard ordering for pre-release identifiers
version_greater_than() {
    local v1=$1
    local v2=$2
    
    # Strip any suffix (e.g., -dev, -alpha, -beta, -rc)
    # Extract only the numeric version part before any hyphen using bash parameter expansion
    local v1_numeric="${v1%%-*}"
    local v2_numeric="${v2%%-*}"
    
    # Extract suffixes using bash parameter expansion
    # Initialize as empty (for versions without suffixes), then conditionally assign
    local v1_suffix=""
    local v2_suffix=""
    [[ "$v1" == *-* ]] && v1_suffix="${v1#*-}"
    [[ "$v2" == *-* ]] && v2_suffix="${v2#*-}"
    
    # Split versions into arrays
    IFS='.' read -ra V1 <<< "$v1_numeric"
    IFS='.' read -ra V2 <<< "$v2_numeric"
    
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
    
    # Numeric versions are equal, check suffixes
    # A version without a suffix (release) is greater than a version with a suffix (pre-release)
    if [ -z "$v1_suffix" ] && [ -n "$v2_suffix" ]; then
        # v1 is release, v2 is pre-release -> v1 > v2
        return 0
    elif [ -n "$v1_suffix" ] && [ -z "$v2_suffix" ]; then
        # v1 is pre-release, v2 is release -> v1 < v2
        return 1
    fi
    
    # Both have suffixes or both don't have suffixes - they're equal
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
    bashio::log.info "Triggering Home Assistant restart to load the updated integration..."
    
    # Trigger Home Assistant restart via Supervisor API
    if [ -n "${SUPERVISOR_TOKEN}" ]; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST \
            -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
            -H "Content-Type: application/json" \
            http://supervisor/core/restart)
        
        if [ "${HTTP_CODE}" = "200" ]; then
            bashio::log.info "Home Assistant restart triggered successfully"
        else
            bashio::log.warning "Failed to trigger Home Assistant restart (HTTP ${HTTP_CODE}). Please restart manually for the integration to be available."
        fi
    else
        bashio::log.warning "SUPERVISOR_TOKEN not available. Please restart Home Assistant manually for the integration to be available."
    fi
else
    bashio::log.info "Custom component installation up to date"
fi

bashio::log.info "Multizone Climate Add-on initialization complete"

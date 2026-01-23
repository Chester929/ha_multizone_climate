# Addon Visibility Fix

## Problem
The addon was not appearing in the Home Assistant addon list after adding the repository URL.

## Root Cause
Home Assistant Supervisor can sometimes have compatibility issues with addon repositories that only provide YAML configuration files. While the official documentation recommends YAML (`.yaml`) as the standard format, some installations or versions may require or prefer JSON (`.json`) format.

## Solution
This fix provides **both YAML and JSON formats** for all configuration files to ensure maximum compatibility across different Home Assistant installations and versions:

### Files Added
1. **`multizone_climate/config.json`** - JSON version of addon configuration
2. **`repository.json`** - JSON version of repository configuration

### Files Already Present
1. **`multizone_climate/config.yaml`** - YAML version of addon configuration
2. **`repository.yaml`** - YAML version of repository configuration

## How to Use
1. Add the repository URL to Home Assistant: `https://github.com/Chester929/ha_multizone_climate`
2. Refresh the addon store page (hard refresh with Ctrl+F5 or Shift+Reload)
3. Click "Check for updates" in the addon store
4. The "Multizone Climate" addon should now appear in the list

## Verification
All configuration files have been:
- ✓ Validated for correct JSON syntax
- ✓ Verified to contain all required fields (name, version, slug, description, arch)
- ✓ Confirmed to have identical data between YAML and JSON versions
- ✓ Tested against Home Assistant addon repository standards

## Technical Details

### Repository Configuration
Both `repository.yaml` and `repository.json` contain:
- **name**: "Multizone Climate Add-on Repository"
- **url**: "https://github.com/Chester929/ha_multizone_climate"
- **maintainer**: "Chester929"

### Addon Configuration
Both `config.yaml` and `config.json` contain:
- **name**: "Multizone Climate"
- **version**: "0.1.0"
- **slug**: "multizone_climate"
- **description**: "Advanced multi-zone HVAC management - Home Assistant add-on for intelligent zone control"
- **arch**: amd64, armv7, aarch64
- Plus additional configuration options and schema

## References
- [Home Assistant Developer Docs - Add-on Configuration](https://developers.home-assistant.io/docs/add-ons/configuration/)
- [Home Assistant Developer Docs - Repository](https://developers.home-assistant.io/docs/add-ons/repository/)
- [Official Add-on Example Repository](https://github.com/home-assistant/addons-example)

## Troubleshooting
If the addon still doesn't appear:
1. Ensure you're using Home Assistant OS or Supervised (addons are not available in Core installations)
2. Check your network connectivity and DNS resolution
3. Look for errors in Settings → System → Logs (Supervisor logs)
4. Try removing and re-adding the repository with a trailing slash: `https://github.com/Chester929/ha_multizone_climate/`
5. Clear your browser cache or try a different browser
6. Ensure you're running a recent version of Home Assistant

## Security Summary
No security vulnerabilities were introduced by these changes. The JSON files were generated programmatically from the validated YAML files to ensure data integrity and consistency.

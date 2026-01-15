# Developer Quick Start

This guide helps developers understand and work with the add-on structure.

## Quick Commands

### Test Add-on Locally

```bash
# Build the add-on container
cd multizone_climate
docker build --build-arg BUILD_FROM="ghcr.io/home-assistant/amd64-base:3.19" -t multizone-climate-test .

# Run it (simulating add-on environment)
docker run --rm \
  -p 6379:6379 \
  -v $(pwd)/test-data:/data \
  -e REDIS_HOST=localhost \
  -e REDIS_PORT=6379 \
  multizone-climate-test
```

### Test Integration Locally

```bash
# Copy to your HA test instance
cp -r multizone_climate/custom_components/multizone_climate /path/to/homeassistant/custom_components/

# Restart HA
# Configure via UI
```

### Validate Configuration

```bash
# Validate add-on config.yaml
docker run --rm -v $(pwd)/multizone_climate:/data \
  homeassistant/amd64-hassio-supervisor \
  /usr/bin/hassio addons validate /data

# Validate integration manifest
python3 -m json.tool multizone_climate/custom_components/multizone_climate/manifest.json
```

## File Modification Guide

### Changing Add-on Configuration Options

**File:** `multizone_climate/config.yaml`

1. Add option to `options:` section (default value)
2. Add schema to `schema:` section (validation)
3. Update `run.sh` to read the new option
4. Update `translations/en.yaml` with description
5. Update `DOCS.md` with documentation
6. Bump version number

### Adding Integration Features

**Files:** `multizone_climate/custom_components/multizone_climate/*.py`

1. Add constants to `const.py`
2. Implement logic in appropriate platform file
3. Update `config_flow.py` if configuration needed
4. Update `manifest.json` version
5. Add translations to `translations/en.yaml` (if UI changes)

### Adding New Platforms

```bash
# Create new platform file
cd multizone_climate/custom_components/multizone_climate
touch binary_sensor.py  # or other platform

# Update __init__.py PLATFORMS list
# Implement async_setup_entry in new file
```

## Testing Checklist

### Add-on Testing
- [ ] Container builds successfully
- [ ] Redis starts and is accessible
- [ ] Integration files are copied correctly
- [ ] Logs show no errors
- [ ] Can restart add-on without issues
- [ ] Configuration options work
- [ ] AppArmor profile doesn't block operations

### Integration Testing
- [ ] Config flow works (both steps)
- [ ] Integration loads without errors
- [ ] Entities are created
- [ ] Options flow works
- [ ] Can reload integration
- [ ] Can remove integration
- [ ] Redis connection succeeds

### Both Methods Testing
- [ ] Add-on method works end-to-end
- [ ] HACS method works with external Redis
- [ ] Same features available in both
- [ ] Documentation is accurate

## Common Tasks

### Update Version

```bash
# Add-on version
sed -i 's/version: ".*"/version: "1.1.0"/' multizone_climate/config.yaml

# Integration version
sed -i 's/"version": ".*"/"version": "1.1.0"/' multizone_climate/custom_components/multizone_climate/manifest.json

# Update changelog
echo "## [1.1.0] - $(date +%Y-%m-%d)" >> multizone_climate/CHANGELOG.md
```

### Add Translation

```bash
# Add new language file
cp multizone_climate/translations/en.yaml multizone_climate/translations/cs.yaml
# Edit cs.yaml with Czech translations

# Update config.yaml if needed (add to list)
```

### Build Multi-Arch

```bash
# Set up buildx
docker buildx create --use

# Build all architectures
cd multizone_climate
docker buildx build \
  --platform linux/amd64,linux/arm/v7,linux/arm64,linux/386 \
  --build-arg BUILD_FROM="ghcr.io/home-assistant/amd64-base:3.19" \
  -t ghcr.io/chester929/ha_multizone_climate:latest \
  --push .
```

## Debugging

### Add-on Logs
```bash
# Via HA UI
Settings → Add-ons → Multizone Climate → Log

# Or via CLI
ha addons logs multizone_climate
```

### Integration Logs
```bash
# Enable debug logging in HA
# configuration.yaml:
logger:
  default: info
  logs:
    custom_components.multizone_climate: debug

# View logs
Settings → System → Logs
# Or check /config/home-assistant.log
```

### Redis Debugging
```bash
# Connect to Redis from add-on
docker exec -it addon_multizone_climate redis-cli

# Check keys
KEYS ha_multizone:*

# Monitor commands
MONITOR

# Check info
INFO
```

## Project Workflow

### Making Changes

1. **Create branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes**
   - Edit files in `multizone_climate/`
   - Update documentation
   - Add tests if applicable

3. **Test locally**
   - Build and run add-on
   - Test integration
   - Verify both methods work

4. **Update docs**
   - Update CHANGELOG.md
   - Update version numbers
   - Update relevant documentation

5. **Commit and push**
   ```bash
   git add .
   git commit -m "Add feature: description"
   git push origin feature/my-feature
   ```

6. **Create PR**
   - Open pull request on GitHub
   - Describe changes
   - Link any issues

### Release Process

1. Update version in:
   - `config.yaml`
   - `manifest.json`
   - `CHANGELOG.md`

2. Commit version bump
   ```bash
   git commit -m "Release v1.1.0"
   git tag v1.1.0
   git push && git push --tags
   ```

3. Build and publish containers
   ```bash
   # CI/CD should handle this, or manually:
   docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 \
     -t ghcr.io/chester929/ha_multizone_climate:1.1.0 \
     -t ghcr.io/chester929/ha_multizone_climate:latest \
     --push .
   ```

4. Create GitHub release
   - Tag: v1.1.0
   - Title: Release 1.1.0
   - Copy CHANGELOG entry to description

## Useful Resources

- [Home Assistant Add-on Development](https://developers.home-assistant.io/docs/add-ons)
- [Integration Development](https://developers.home-assistant.io/docs/development_index)
- [Config Flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler)
- [Climate Entity](https://developers.home-assistant.io/docs/core/entity/climate/)
- [Bashio](https://github.com/hassio-addons/bashio) - Shell functions for add-ons

## Repository Structure

```
ha_multizone_climate/
├── README.md                    # Overview
├── INSTALLATION.md              # User installation guide
├── DIAGRAMS.md                  # Technical documentation
├── PROJECT_STRUCTURE.md         # Structure explanation
├── ADDON_STRUCTURE_EXPLAINED.md # Q&A about add-on structure
├── DEVELOPER_QUICK_START.md     # This file
│
└── multizone_climate/           # Add-on + Integration
    ├── config.yaml              # Add-on config
    ├── Dockerfile               # Container definition
    ├── build.yaml               # Multi-arch builds
    ├── run.sh                   # Startup script
    ├── translations/            # UI translations
    └── custom_components/       # HA Integration
        └── multizone_climate/   # Integration code
```

## Next Steps

1. Implement core integration functionality
2. Add comprehensive tests
3. Create custom Lovelace cards
4. Add more language translations
5. Set up CI/CD for automated builds
6. Publish to community add-on repository

## Getting Help

- Check existing documentation
- Review Home Assistant developer docs
- Ask in Home Assistant developer Discord
- Open an issue on GitHub

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly (both add-on and integration methods)
5. Update documentation
6. Submit a pull request

---

**Happy developing! 🚀**

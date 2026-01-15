# Project Structure

This document explains how the `ha_multizone_climate` repository is organized to support both Home Assistant add-on and HACS custom integration installation methods.

## Overview

```
ha_multizone_climate/
├── README.md                          # Main documentation with installation methods
├── INSTALLATION.md                    # Detailed installation guide
├── DIAGRAMS.md                        # System architecture and algorithms
├── .gitignore                         # Git ignore rules
├── .github/                           # GitHub workflows and actions
│   └── workflows/
│       └── generate-diagrams-pdf.yml  # Auto-generate PDF from diagrams
│
└── multizone_climate/                 # HOME ASSISTANT ADD-ON ROOT
    ├── config.yaml                    # Add-on metadata and configuration schema
    ├── Dockerfile                     # Container build instructions
    ├── build.yaml                     # Multi-architecture build configuration
    ├── run.sh                         # Add-on startup script (runs Redis + installs integration)
    ├── apparmor.txt                   # Security profile for the add-on
    ├── DOCS.md                        # Add-on user documentation
    ├── README.md                      # Add-on specific readme
    ├── CHANGELOG.md                   # Add-on version history
    ├── icon.png                       # Add-on icon (256x256)
    ├── logo.png                       # Add-on logo
    │
    ├── translations/                  # Add-on configuration translations
    │   ├── en.yaml                    # English translations
    │   ├── cs.yaml                    # Czech (planned)
    │   ├── sk.yaml                    # Slovak (planned)
    │   └── pl.yaml                    # Polish (planned)
    │
    └── custom_components/             # Home Assistant custom integration
        └── multizone_climate/         # Integration package
            ├── manifest.json          # Integration metadata
            ├── __init__.py            # Integration entry point
            ├── config_flow.py         # Configuration UI flow
            ├── const.py               # Constants and defaults
            ├── climate.py             # Climate platform (main + zones)
            ├── sensor.py              # Sensor platform (monitoring)
            ├── switch.py              # Switch platform (multizone enable)
            ├── coordinator.py         # Data update coordinator (planned)
            ├── redis_client.py        # Redis connection manager (planned)
            ├── core_logic.py          # Core algorithms implementation (planned)
            ├── background_jobs.py     # Async job processing (planned)
            ├── services.yaml          # Service definitions (planned)
            ├── strings.json           # UI translations (planned)
            └── translations/          # Integration translations (planned)
                └── en.json
```

## Key Directories

### Root Level
- Contains main documentation and guides
- GitHub workflows for automation
- Single add-on directory for the entire project

### `multizone_climate/` - Add-on Directory
This is the **Home Assistant Add-on** root. It contains:
- Add-on configuration and metadata
- Docker container definition
- Startup scripts
- Documentation specific to add-on usage
- The custom integration bundled inside

### `multizone_climate/custom_components/multizone_climate/` - Integration
This is the **Custom Integration** that can be:
1. **Auto-installed by the add-on** to `/config/custom_components/`
2. **Manually installed via HACS** or direct copy to Home Assistant

## Installation Paths

### Method 1: Add-on Installation
When installed as an add-on:
```
/addons/multizone_climate/          # Add-on files
/config/custom_components/          # Integration auto-copied here by run.sh
    └── multizone_climate/
```

### Method 2: HACS Installation
When installed via HACS:
```
/config/custom_components/          # User manually installs here
    └── multizone_climate/          # Copied from repository
```

## File Purposes

### Add-on Files

| File | Purpose |
|------|---------|
| `config.yaml` | Defines add-on metadata, options schema, architecture support |
| `Dockerfile` | Instructions to build the container (Redis + Python + integration) |
| `build.yaml` | Multi-arch build configuration for different platforms |
| `run.sh` | Startup script: launches Redis, optionally installs integration |
| `apparmor.txt` | Security profile (required for some HA installations) |
| `DOCS.md` | User-facing documentation shown in add-on store |
| `README.md` | Add-on specific readme |
| `CHANGELOG.md` | Version history and release notes |
| `icon.png` | 256x256 icon for add-on UI |
| `logo.png` | Logo for add-on store |
| `translations/*.yaml` | UI translations for add-on configuration options |

### Integration Files

| File | Purpose |
|------|---------|
| `manifest.json` | Integration metadata (domain, version, requirements) |
| `__init__.py` | Entry point, setup/unload logic |
| `config_flow.py` | UI-based configuration wizard |
| `const.py` | Constants, defaults, configuration keys |
| `climate.py` | Climate entities (main climate + zone climates) |
| `sensor.py` | Sensor entities for monitoring |
| `switch.py` | Switch entity (multizone enable/disable) |
| `coordinator.py` | Manages data updates and background jobs (planned) |
| `redis_client.py` | Redis connection and operations (planned) |
| `core_logic.py` | Core algorithms (calculate temp, update valves) (planned) |
| `background_jobs.py` | Async job processing (planned) |
| `services.yaml` | Service definitions (add_zone, remove_zone, etc.) (planned) |
| `strings.json` | Integration UI text (planned) |
| `translations/*.json` | Integration UI translations (planned) |

## Development Workflow

### For Add-on Development
1. Modify files in `multizone_climate/`
2. Test with `docker build` or direct add-on installation
3. Update `CHANGELOG.md`
4. Bump version in `config.yaml`

### For Integration Development
1. Modify files in `multizone_climate/custom_components/multizone_climate/`
2. Test by copying to `/config/custom_components/` in test HA instance
3. Update integration version in `manifest.json`
4. Test both installation methods

### For Documentation
1. Update main `README.md` for general info
2. Update `INSTALLATION.md` for setup procedures
3. Update `DIAGRAMS.md` for technical architecture
4. Update add-on `DOCS.md` for add-on specific info

## Distribution

### Add-on Distribution
- Users add repository URL to their add-on store
- Home Assistant pulls add-on from GitHub
- Add-on store shows metadata from `config.yaml`
- Container built from `Dockerfile` or pulled from registry

### Integration Distribution
- **Via Add-on**: Automatically installed by `run.sh`
- **Via HACS**: Users add as custom repository
- **Manual**: Users copy `custom_components/multizone_climate/` to their HA

## Version Management

Two version numbers to maintain:
1. **Add-on version** in `multizone_climate/config.yaml`
2. **Integration version** in `multizone_climate/custom_components/multizone_climate/manifest.json`

These can be kept in sync or versioned independently.

## Future Structure Additions

Planned additions to the structure:

```
multizone_climate/
└── custom_components/
    └── multizone_climate/
        ├── tests/                     # Unit and integration tests
        │   ├── test_core_logic.py
        │   ├── test_config_flow.py
        │   └── test_climate.py
        ├── frontend/                  # Custom Lovelace cards
        │   ├── multizone-card.js
        │   └── zone-card.js
        └── locales/                   # Full translations
            ├── en.json
            ├── cs.json
            ├── sk.json
            └── pl.json
```

## Best Practices

1. **Keep integration self-contained**: All integration code in `custom_components/multizone_climate/`
2. **Document both methods**: Ensure docs work for add-on and HACS users
3. **Test both paths**: Verify add-on auto-install and manual install
4. **Version carefully**: Keep version numbers coordinated
5. **Maintain compatibility**: Integration should work standalone (with external Redis)

## Questions & Answers

**Q: Can the integration work without the add-on?**  
A: Yes, if the user provides their own Redis server.

**Q: Can I use the add-on just for Redis?**  
A: Yes, set `install_integration: false` in add-on config and install integration separately.

**Q: Why is the integration inside the add-on directory?**  
A: So the add-on can bundle and auto-install it. The same code can be extracted and used standalone.

**Q: How do I publish this?**  
A: 
- Add-on: Users add repo URL to add-on store
- HACS: Register with HACS or users add as custom repository
- Both: Publish to Home Assistant Community Store and add-on repository index

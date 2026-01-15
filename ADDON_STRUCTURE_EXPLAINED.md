# Home Assistant Add-on: Question & Answer

## Question
**"Can it be as an hassio addon ? If yes, how project structure will looks like ?"**

## Answer

**YES**, this project can absolutely be structured as a Home Assistant add-on, and has been designed to support **both** installation methods:

1. **Home Assistant Add-on** (includes Redis)
2. **HACS Custom Integration** (user provides Redis)

## How It Works

### The Dual-Purpose Design

The project uses a **nested structure** where:
- The **outer layer** is a Home Assistant add-on that provides Redis
- The **inner layer** is a custom integration that can work standalone
- The add-on **bundles** the integration and can auto-install it

### Visual Structure

```
ha_multizone_climate/                    ← Git Repository Root
│
├── README.md                            ← Main docs (explains both methods)
├── INSTALLATION.md                      ← Detailed setup guide
├── DIAGRAMS.md                          ← Technical documentation
├── PROJECT_STRUCTURE.md                 ← This explanation
│
└── multizone_climate/                   ← HOME ASSISTANT ADD-ON ROOT ✨
    │
    ├── config.yaml                      ← Add-on metadata
    ├── Dockerfile                       ← Builds container with Redis
    ├── build.yaml                       ← Multi-arch support
    ├── run.sh                           ← Starts Redis + installs integration
    ├── apparmor.txt                     ← Security profile
    ├── DOCS.md                          ← Add-on user docs
    ├── CHANGELOG.md                     ← Version history
    ├── icon.png                         ← Add-on icon
    ├── logo.png                         ← Add-on logo
    │
    ├── translations/                    ← Add-on config translations
    │   └── en.yaml
    │
    └── custom_components/               ← CUSTOM INTEGRATION (nested inside)
        └── multizone_climate/
            ├── manifest.json            ← Integration metadata
            ├── __init__.py              ← Entry point
            ├── config_flow.py           ← UI configuration
            ├── const.py                 ← Constants
            ├── climate.py               ← Climate entities
            ├── sensor.py                ← Sensors
            └── switch.py                ← Multizone enable switch
```

## Key Files Explained

### Add-on Essential Files

| File | Purpose | Required |
|------|---------|----------|
| `config.yaml` | Add-on metadata, configuration schema, supported architectures | ✅ Yes |
| `Dockerfile` | Container build (installs Redis, Python, integration) | ✅ Yes |
| `build.yaml` | Multi-architecture build settings | Recommended |
| `run.sh` | Startup script - launches Redis, auto-installs integration | ✅ Yes |
| `apparmor.txt` | Security profile for supervised installations | Recommended |
| `DOCS.md` | User documentation shown in add-on store | Recommended |
| `icon.png` | 256x256 icon for UI | Recommended |
| `logo.png` | Logo for add-on store | Recommended |

### Integration Files (Can Work Standalone)

All files in `custom_components/multizone_climate/` make up the integration that:
- Can be **auto-installed** by the add-on to `/config/custom_components/`
- Can be **manually installed** via HACS or direct copy
- Works with **any Redis instance** (add-on's or external)

## How Users Install It

### Method 1: As an Add-on 🎉

```
1. User adds repository URL to HA add-on store
2. Installs "Multizone Climate" add-on
3. Add-on starts → Redis launches
4. run.sh copies integration to /config/custom_components/
5. User restarts HA
6. User configures integration via UI
7. ✅ Done! Redis + Integration working
```

**Benefits:**
- Redis included automatically
- One-click installation
- No external dependencies
- Perfect for beginners

### Method 2: As a HACS Integration 🔧

```
1. User ensures they have Redis running somewhere
2. Installs integration via HACS or manually
3. Restarts HA
4. Configures integration with Redis connection details
5. ✅ Done! Integration connected to user's Redis
```

**Benefits:**
- Use existing Redis infrastructure
- More control over Redis configuration
- Smaller footprint
- Better for advanced users

## Technical Details

### Add-on Configuration Schema

From `config.yaml`:
```yaml
options:
  redis_host: "localhost"
  redis_port: 6379
  redis_password: ""
  redis_db: 0
  redis_key_prefix: "ha_multizone"
  install_integration: true    # Auto-install integration
  log_level: "info"
```

### Multi-Architecture Support

The add-on supports:
- **amd64** - Intel/AMD 64-bit
- **armv7** - ARM 32-bit (Raspberry Pi 3/4)
- **aarch64** - ARM 64-bit
- **i386** - Intel 32-bit (legacy)

Built using different base images via `build.yaml`.

### What Happens at Startup

The `run.sh` script:
1. Reads configuration from add-on options
2. Starts Redis server with configured settings
3. Waits for Redis to be ready
4. If `install_integration: true`:
   - Copies integration files from `/app/custom_components/` to `/config/custom_components/`
   - Logs instructions to restart HA
5. Keeps running to maintain Redis

### Integration Independence

The integration in `custom_components/multizone_climate/`:
- **Does NOT depend on the add-on**
- Just needs **any Redis instance** (localhost or remote)
- Configured via HA UI with Redis connection details
- Can be used completely standalone

## File Locations

### In the Repository
```
ha_multizone_climate/
└── multizone_climate/                      # Add-on root
    └── custom_components/multizone_climate/  # Integration source
```

### After Add-on Installation
```
# Inside add-on container:
/app/custom_components/multizone_climate/   # Integration source
/data/redis/                                # Redis data

# In Home Assistant:
/config/custom_components/multizone_climate/  # Integration (copied by run.sh)
```

### After HACS Installation
```
# In Home Assistant:
/config/custom_components/multizone_climate/  # Integration (from HACS/manual)
```

## Distribution

### Publishing as Add-on
1. Users add repository URL to their add-on store
2. Or publish to [Community Add-ons](https://github.com/hassio-addons)
3. HA Supervisor pulls from GitHub and builds container

### Publishing as HACS Integration
1. Register with HACS default repositories
2. Or users add as custom HACS repository
3. HACS downloads integration files to custom_components

## Why This Structure?

✅ **Flexibility**: Supports both novice and advanced users  
✅ **Convenience**: Beginners get Redis automatically  
✅ **Control**: Advanced users can use external Redis  
✅ **Maintainability**: Single codebase for both methods  
✅ **Standard**: Follows Home Assistant best practices

## Comparison with Other Projects

### Similar Dual-Purpose Add-ons:
- **Zigbee2MQTT**: Add-on provides MQTT broker, integration connects to it
- **Node-RED**: Add-on runs Node-RED server, HA integrates via websocket
- **AppDaemon**: Add-on provides AppDaemon environment, apps use HA API

### Unique Aspects:
- Integration is **bundled inside** the add-on
- Add-on **auto-installs** the integration
- Integration works **standalone** without the add-on

## Future Enhancements

Potential additions to the structure:
```
multizone_climate/
└── custom_components/multizone_climate/
    ├── tests/                  # Unit tests
    ├── frontend/               # Custom Lovelace cards  
    ├── locales/                # Full translations
    ├── coordinator.py          # Data coordinator
    ├── redis_client.py         # Redis client
    ├── core_logic.py           # Algorithms
    └── background_jobs.py      # Job processing
```

## Summary

**Yes, this project IS structured as a Home Assistant add-on!**

The structure enables:
- ✅ Add-on installation (Redis bundled)
- ✅ HACS installation (standalone)
- ✅ Multi-architecture support
- ✅ Auto-installation of integration
- ✅ Standalone integration capability

**See these files for more details:**
- [`INSTALLATION.md`](../INSTALLATION.md) - How to install
- [`PROJECT_STRUCTURE.md`](../PROJECT_STRUCTURE.md) - Detailed structure
- [`multizone_climate/DOCS.md`](../multizone_climate/DOCS.md) - Add-on docs
- [`multizone_climate/config.yaml`](../multizone_climate/config.yaml) - Add-on config

**The answer to "how project structure will looks like?" →** It looks exactly like the structure shown above! 🎉

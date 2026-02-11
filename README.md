# Multizone Climate Control for Home Assistant

Home Assistant integration for intelligent multi-zone HVAC climate control with autonomous zone management and hybrid valve control.

## 📖 Documentation

All documentation has been consolidated into the `docs/` directory:

**👉 [Start Here: Documentation Index](docs/README.md)**

### Quick Links

- **[FINAL_APPROVED_SOLUTION.md](docs/current/FINAL_APPROVED_SOLUTION.md)** - Complete architecture specification
- **[IMPLEMENTATION_ROADMAP.md](docs/current/IMPLEMENTATION_ROADMAP.md)** - Step-by-step implementation plan
- **[INDEX_IMPLEMENTATION_READY.md](docs/current/INDEX_IMPLEMENTATION_READY.md)** - Navigation guide

## 🎯 Key Features

### Dual Zone Control (A1 + A2 Combined)
- **A1**: User can call `climate.turn_on/off` service on zone entities
- **A2**: Valve switch state changes automatically enable/disable zones
- Both mechanisms work simultaneously for maximum flexibility

### Dual Climate Override (B1 + B2)
- **B1**: Immediate event listener override (< 1s) when user manually changes main climate target
- **B2**: Regular coordinator updates for normal operation
- Smart distinction between manual changes and system updates

### Safety Features
- Multiple fallback zone support (≥ min_valves_open required)
- Delayed zone disable with remaining time calculation
- Fallback protection prevents safety violations
- Immediate recalculation on zone state changes

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Main Climate                       │
│  (Manages water temperature for entire system)     │
└──────────────┬──────────────────────────────────────┘
               │
    ┌──────────┴────────────┬──────────────┐
    │                       │              │
┌───▼────┐            ┌────▼─────┐   ┌───▼────┐
│ Zone 1 │            │  Zone 2  │   │ Zone 3 │
│ (Room) │            │  (Room)  │   │ (Room) │
└────────┘            └──────────┘   └────────┘
    │                      │              │
┌───▼────┐            ┌────▼─────┐   ┌───▼────┐
│ Valve  │            │  Valve   │   │ Valve  │
│ Switch │            │  Switch  │   │ Switch │
└────────┘            └──────────┘   └────────┘
```

### Autonomous Zone Control

Each zone:
- Monitors its own temperature sensor
- Calculates its own satisfaction state (underheated/satisfied/overheated)
- Controls its own valve based on hybrid logic
- Can be enabled/disabled via climate service OR valve switch
- Responds immediately to state changes (< 1s)

### Main Climate Management

The main climate:
- Calculates target based on enabled zones' deficits
- Overrides manual changes immediately via event listener
- Updates regularly via coordinator for normal operation
- Maintains system safety through fallback protection

## 🚀 Implementation Status

**Current Status**: ✅ Architecture Complete & Approved

The solution combines dual mechanisms for both zone control and climate override, providing maximum flexibility while maintaining safety and immediate responsiveness.

**Next Steps**:
1. Review [FINAL_APPROVED_SOLUTION.md](docs/current/FINAL_APPROVED_SOLUTION.md)
2. Follow [IMPLEMENTATION_ROADMAP.md](docs/current/IMPLEMENTATION_ROADMAP.md)
3. Begin Phase 1 implementation

## 📋 Requirements

- Home Assistant 2024.1+
- Redis (for state management)
- Zigbee valve switches
- Temperature sensors per zone

## 📞 Support

For questions or issues:
- Review the [documentation](docs/README.md)
- Check [archived documentation](docs/archive/) for design evolution context
- Refer to implementation roadmap for execution guidance

---

**Last Updated**: 2026-02-11  
**Status**: Implementation Ready  
**Documentation**: Consolidated in `docs/`

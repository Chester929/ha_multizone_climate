# Multizone Climate Control for Home Assistant

Home Assistant integration for intelligent multi-zone HVAC climate control with autonomous zone management and hybrid valve control.

## 📖 Documentation

**👉 [Complete System Documentation](docs/COMPLETE_MULTIZONE_CLIMATE_DOCUMENTATION.md)** - **NEW v1.0!**

All documentation has been consolidated into a single comprehensive guide covering:
- System architecture and design decisions
- Complete hardware specifications (DE DIETRICH STRATEO 4 R32, Sonoff MINI-ZB2GS)
- Dual control mechanisms (A1+A2 zone control, B1+B2 climate override)
- Implementation guidance with code examples

### Quick Links

- **[Complete Documentation v1.0](docs/COMPLETE_MULTIZONE_CLIMATE_DOCUMENTATION.md)** ⭐ Start here
- [Legacy Documentation](docs/current/) - Previous documentation (superseded by v1.0)

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
1. Review [Complete Documentation v1.0](docs/COMPLETE_MULTIZONE_CLIMATE_DOCUMENTATION.md)
2. Check [V1.0 Completion Summary](docs/V1.0_COMPLETE_SUMMARY.md)
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

**Last Updated**: 2026-02-19  
**Status**: Implementation Ready  
**Documentation**: Consolidated v1.0 in `docs/`

# Architecture Decision Summary

## Quick Reference

This document summarizes the key architectural decisions made in PROJECT_STRUCTURE.md.

---

## ✅ Decision: Custom Home Assistant Integration (via HACS)

### What We're Building:
- **Custom Integration**: Installed via HACS (Home Assistant Community Store)
- **Native Entities**: Climate, sensor, switch, and binary_sensor platforms
- **Custom Frontend**: Lovelace cards packaged within the integration
- **External Dependency**: Redis (user-provided)

### Why Not an Add-on?
| Feature | Custom Integration ✅ | Add-on ❌ |
|---------|---------------------|----------|
| Works on all HA installations | Yes | No (Supervisor only) |
| Easy installation | HACS | Two-step process |
| Native entity integration | Yes | Requires bridge |
| Update mechanism | HACS | Supervisor |

---

## 📁 Project Structure Overview

```
ha_multizone_climate/
├── custom_components/multizone_climate/  # Main integration code
│   ├── core/                             # Algorithms & logic
│   ├── jobs/                             # Background jobs
│   ├── platforms/                        # HA entities
│   ├── translations/                     # i18n (en, cs, sk, pl)
│   └── www/                              # Frontend assets (bundled)
│
├── frontend/                             # Frontend source (TypeScript)
│   ├── src/cards/                        # Lovelace cards
│   ├── src/components/                   # UI components
│   └── package.json                      # Build system
│
├── tests/                                # Test suite
│   ├── unit/                             # Unit tests
│   ├── integration/                      # Integration tests
│   └── scenarios/                        # Scenario tests
│
└── docs/                                 # Documentation
```

---

## 🎨 Frontend Components

### Three Custom Lovelace Cards:
1. **Zone Climate Card** - Individual zone control and status
2. **Main Climate Card** - Main HVAC control and multizone toggle
3. **Dashboard Panel** - Full monitoring dashboard

### Technology Stack:
- **Language**: TypeScript
- **Framework**: Lit (Home Assistant standard)
- **Build**: Rollup
- **Output**: Bundled JavaScript in `custom_components/multizone_climate/www/`

---

## 🗄️ Redis Integration

### Approach: External Dependency
- **Not bundled** with the integration
- **User-provided** via:
  - Home Assistant Redis add-on (Supervisor users)
  - External Redis server (Docker/Core users)

### Why External?
- Keeps integration lightweight
- Users may already have Redis
- Flexibility in deployment
- No supervisor dependency

---

## 🧪 Testing Strategy

### Three Test Levels:
1. **Unit Tests** (95%+ coverage for core logic)
   - Algorithms, valve control, safety checks
   
2. **Integration Tests** (80%+ coverage)
   - Config flow, platforms, coordinator
   
3. **Scenario Tests** (End-to-end)
   - Temperature drop, valve swapping, cooling mode

### Test Infrastructure:
- pytest + pytest-homeassistant-custom-component
- Mock Redis for unit tests
- Real Redis for integration tests

---

## 📦 HACS Compatibility

### Required Files:
- ✅ `hacs.json` - HACS metadata
- ✅ `manifest.json` - Integration manifest
- ✅ `info.md` - HACS info page
- ✅ `README.md` - Project readme

### Installation:
1. Add custom repository to HACS
2. Search for "Multizone Climate"
3. Click install
4. Restart Home Assistant
5. Add integration via UI

---

## 🚀 Development Workflow

### Setup:
```bash
git clone https://github.com/Chester929/ha_multizone_climate.git
pip install -r requirements_dev.txt
cd frontend && npm install && npm run build
```

### Testing:
```bash
pytest                                    # All tests
pytest --cov                              # With coverage
pytest tests/unit/test_algorithms.py      # Specific test
```

### Code Quality:
```bash
pylint custom_components/multizone_climate/
black custom_components/multizone_climate/
mypy custom_components/multizone_climate/
```

---

## 📋 Key Design Principles

1. **Modularity**: Separate concerns (core logic, jobs, platforms)
2. **Testability**: High test coverage, mockable components
3. **Maintainability**: Clear structure, good documentation
4. **Compatibility**: Works on all HA installations
5. **User-Friendly**: Easy installation via HACS, intuitive UI
6. **Performance**: Redis for fast state management, efficient job queuing
7. **Safety**: Multiple safety checks, minimum valve enforcement

---

## 🔄 Development Roadmap

### Phase 1: Core Implementation
- [ ] Redis client
- [ ] Core algorithms
- [ ] Config flow
- [ ] Climate platform

### Phase 2: Background Jobs
- [ ] Job base class
- [ ] Calculate main temp job
- [ ] Update valves job
- [ ] Safety check job

### Phase 3: Frontend
- [ ] Zone climate card
- [ ] Main climate card
- [ ] Dashboard panel

### Phase 4: Testing & Polish
- [ ] Unit tests
- [ ] Integration tests
- [ ] Scenario tests
- [ ] Documentation

### Phase 5: HACS Release
- [ ] HACS submission
- [ ] First stable release

---

## ❓ Questions & Answers

### Q: Can I use this without Redis?
A: Currently no. Redis is required for job queuing and state management. Future versions may support alternatives.

### Q: Will this work with Home Assistant Container?
A: Yes! It's a custom integration that works on all HA installations (Supervisor, Docker, Core, Container).

### Q: How do I update the integration?
A: Via HACS. When a new version is released, HACS will notify you and you can update with one click.

### Q: Can I contribute?
A: Yes! See CONTRIBUTING.md (to be created) for guidelines.

---

## 📚 Reference Documents

- **PROJECT_STRUCTURE.md** - Complete project structure (this summary's source)
- **DIAGRAMS.md** - System architecture diagrams
- **README.md** - Project overview and algorithms
- **IMPLEMENTATION_SUMMARY.md** - Workflow implementation summary

---

**Last Updated**: 2026-01-15

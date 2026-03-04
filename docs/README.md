# Documentation Index

Welcome to the Multizone Climate Control documentation.

## 📖 Primary Documentation — Single Source of Truth

**⭐ [COMPLETE SYSTEM DOCUMENTATION v1.3](COMPLETE_MULTIZONE_CLIMATE_DOCUMENTATION.md)**

This is the **single authoritative source of truth** for the multizone climate system.
All architecture decisions, code examples, and implementation specifications live here.
When any other document contradicts this one, **this document takes precedence**.

### What's in v1.3?
- **Executive Summary** - Strategic overview, all 6 key decisions, quick start
- **HVAC System Overview** - Hardware introduction (partial; remaining subsections planned)
- **System Architecture** - Component design, data flows, state management
- **Technical Specifications** - **COMPLETE DUAL MECHANISMS** (with bug fixes)
  - **Dual Zone Control (A1+A2)** - Complete implementation guide
  - **Dual Climate Override (B1+B2)** - Complete implementation guide

### v1.3 Correction Highlights
v1.3 reverts an incorrect fix from v1.2:
- ✅ **Temperature semantics corrected** — `climate.main_thermostat` is a room-temperature
  thermostat; constraints restored to room-temperature range (15–30 °C, configurable via
  `min_target_temp` / `max_target_temp`).  The v1.2 water-temperature ranges were wrong.
- ✅ **Overtargeting concept documented** — main thermostat is set to the highest zone
  target so the heat pump keeps running until the most-demanding zone is satisfied.

### v1.2 Bug-Fix Highlights (still in effect)
- ✅ B1 threshold standardised to **2 s** throughout (was inconsistently 1 s in places)
- ✅ `get_available_fallback()` preference logic **fixed** (now prefers already-opening fallbacks)
- ✅ `IndexError` guard added to `get_available_fallback()`
- ✅ `asyncio.create_task()` replaced with `hass.async_create_task()` in data-flow diagram
- ✅ `valve_state_changed_at` timestamp responsibility clarified
- ✅ A2 feedback-loop risk documented with `_system_valve_change` guard pattern
- ✅ **Cooling mode algorithm added** to `_calculate_main_target()`
- ✅ Startup race condition fixed in `_is_manual_change()`
- ✅ Edge Case 2 in §4.2.7 corrected (second rapid change is ignored, not re-detected)

## 📚 Version History

| Version | Date | Lines | Content |
|---------|------|-------|---------|
| **v1.3** | 2026-03-04 | ~3000 | ✅ Correction — v1.2 fix #8 reverted; room-temp semantics restored |
| v1.2 | 2026-03-04 | ~3000 | Bug-fix release — critical and medium errors corrected |
| v1.1 | 2026-02-19 | 2894 | B1+B2 dual override added |
| v1.0 | 2026-02-19 | 2323 | Initial consolidation |

## 📚 Legacy Documentation (Superseded)

The following documents are preserved for historical reference only.
They have been superseded by the v1.3 comprehensive documentation.
**Do not use these as implementation references** — use the primary document above.

- **[current/](current/)** - Previous version 3.0 documentation (4 files)
  - `FINAL_APPROVED_SOLUTION.md` — ⚠️ Superseded; contains known bugs (see notice inside)
  - `IMPLEMENTATION_ROADMAP.md` — Phase plan (still useful as a roadmap reference)
  - `INDEX_IMPLEMENTATION_READY.md` — Navigation guide
  - `REFINEMENT_DELAYED_ZONE_DISABLE.md` — Delayed disable rationale

- **[archive/](archive/)** - Historical documentation (24 files)
  - Generation 1: Initial design and Option 3
  - Generation 2: Simplification and validation

⚠️ **Note**: `current/INDEX_IMPLEMENTATION_READY.md` still refers to
`FINAL_APPROVED_SOLUTION.md` as "⭐ MAIN DOCUMENT". This is outdated — the
primary document is `COMPLETE_MULTIZONE_CLIMATE_DOCUMENTATION.md` v1.3.

## 🚀 Quick Start

1. Read [COMPLETE_MULTIZONE_CLIMATE_DOCUMENTATION.md](COMPLETE_MULTIZONE_CLIMATE_DOCUMENTATION.md)
2. Review Section I (Executive Summary) for strategic overview
3. Review Section II (HVAC System Overview) for hardware requirements
4. Review Section III (System Architecture) for component design
5. Review Section IV (Technical Specifications) for implementation:
   - Section IV.1 for Zone Control (A1+A2)
   - Section IV.2 for Climate Override (B1+B2)

## 📋 Release Summary

- **[V1.0_COMPLETE_SUMMARY.md](V1.0_COMPLETE_SUMMARY.md)** - Summary for original v1.0/v1.1 release

## 📋 Future Enhancements

v1.3 provides complete dual mechanism technical specifications. Future versions will add:
- **v1.4**: Additional Section IV sections (Configuration Schema, Entity Specifications)
- **Business Logic**: 8 detailed scenarios (Section V)
- **Implementation Plan**: Complete 5-phase roadmap (Section VI)
- **Testing Strategy**: Unit and integration testing (Section VII)
- **Security**: Security requirements and best practices (Section VIII)
- **Developer Guide**: Advanced topics and troubleshooting (Sections IX–X)

---

**Current Version**: 1.3  
**Status**: Sections I–IV.2 complete; critical/medium bugs corrected; temperature semantics corrected ✅  
**Last Updated**: 2026-03-04

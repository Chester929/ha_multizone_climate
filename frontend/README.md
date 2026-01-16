# Multizone Climate Frontend

This directory contains the frontend Lovelace cards for the Multizone Climate integration.

## Pre-built Assets

The `dist/` directory contains pre-built JavaScript bundles ready for use:
- `multizone-climate-card.js` - Zone climate display card
- `main-climate-card.js` - Main climate information card
- `dashboard-panel.js` - All zones overview panel

These are automatically included with the integration. No manual installation required.

## Building from Source

If you want to rebuild the frontend assets:

```bash
cd frontend
npm install
npm run build
```

The built files will be output to the `dist/` directory.

## Development

To watch for changes and rebuild automatically:

```bash
npm run watch
```

## Cards

### Multizone Climate Card

The main card for displaying zone climate information.

**Configuration:**
```yaml
type: custom:multizone-climate-card
entity: climate.bedroom_zone
```

## Installation

The built JavaScript files are automatically included with the integration. No manual installation is required.

## Technologies

- **TypeScript**: Type-safe development
- **Lit**: Web components framework
- **Rollup**: Module bundler
- **Terser**: Code minification

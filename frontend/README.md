# Multizone Climate Frontend

This directory contains the frontend Lovelace cards for the Multizone Climate integration.

## Building

To build the frontend assets:

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

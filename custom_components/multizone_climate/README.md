# Multizone Climate - Custom Component

## Installation

This is a Home Assistant **Custom Integration** that provides entity selectors with search and filtering during setup.

### Method 1: HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right
4. Select "Custom repositories"
5. Add this repository URL
6. Install "Multizone Climate"
7. Restart Home Assistant

### Method 2: Manual Installation

1. Copy the `custom_components/multizone_climate` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings** → **Devices & Services**
2. Click **"+ ADD INTEGRATION"**
3. Search for "Multizone Climate"
4. Follow the configuration wizard:
   - **Step 1**: Select your main climate entity (searchable dropdown with climate entities)
   - **Step 2**: Configure your first zone:
     - Zone name
     - Temperature sensor (searchable dropdown with sensor entities)
     - Valve switch (searchable dropdown with **both switch AND valve** entities)
     - Climate entity (optional)
     - Target temperature
     - Priority

5. After initial setup, you can:
   - Click **"CONFIGURE"** to modify settings
   - Add more zones by adding the integration again

## Features

✅ **Searchable entity selectors** with automatic filtering by domain
✅ **Valve switch** supports both `switch` and `valve` entity types
✅ **Climate entity** automatically filtered to climate domain  
✅ **Temperature sensor** filtered to sensor domain
✅ **Friendly names** displayed with entity IDs
✅ **Configuration UI** - all setup done through Home Assistant UI, not YAML

## Entity Domain Filtering

- **Main Climate Entity**: Filtered to `climate` domain only
- **Temperature Sensor**: Filtered to `sensor` domain only
- **Valve Switch**: Filtered to **both** `switch` AND `valve` domains
- **Zone Climate Entity** (optional): Filtered to `climate` domain only

All selectors are searchable dropdown menus with auto-complete.

/**
 * Main Climate Card for Home Assistant.
 * 
 * Displays main climate information:
 * - Current temperature
 * - Target temperature
 * - Outdoor temperature
 * - HVAC mode and action
 * - Multizone enabled status
 * - Number of active zones
 */

import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('multizone-main-climate-card')
export class MultizoneMainClimateCard extends LitElement {
  /**
   * Entity ID for the main climate entity.
   */
  @property({ type: String })
  entity?: string;

  /**
   * Card configuration from Lovelace UI editor.
   */
  @property({ type: Object })
  config?: any;

  /**
   * Home Assistant instance.
   */
  @property({ type: Object })
  hass?: any;

  /**
   * Set configuration from Lovelace editor.
   * 
   * @param config - Card configuration
   */
  setConfig(config: any): void {
    // Validate required fields
    if (!config.entity) {
      throw new Error('You must specify an entity');
    }
    
    // Validate entity is a climate entity
    if (!config.entity.startsWith('climate.')) {
      throw new Error('Entity must be a climate entity');
    }
    
    // Store validated config
    this.config = config;
    this.entity = config.entity;
  }

  /**
   * Render card HTML.
   * 
   * Returns:
   *   Card HTML template
   */
  render() {
    if (!this.hass || !this.entity) {
      return html`
        <ha-card>
          <div class="card-content">
            <div class="warning">Entity not configured</div>
          </div>
        </ha-card>
      `;
    }

    // Get entity state from Home Assistant
    const entityState = this.hass.states[this.entity];
    
    if (!entityState) {
      return html`
        <ha-card>
          <div class="card-content">
            <div class="warning">Entity not found: ${this.entity}</div>
          </div>
        </ha-card>
      `;
    }

    // Extract attributes
    const currentTemp = entityState.attributes.current_temperature;
    const targetTemp = entityState.attributes.temperature;
    const outdoorTemp = entityState.attributes.outdoor_temperature;
    const hvacMode = entityState.state;
    const hvacAction = entityState.attributes.hvac_action;
    const multizoneEnabled = entityState.attributes.multizone_enabled;
    const activeZones = entityState.attributes.active_zones || 0;

    // Format temperatures
    const formatTemp = (temp: number | undefined) => {
      if (temp === undefined || temp === null) return 'N/A';
      return `${temp.toFixed(1)}°C`;
    };

    // Get status color based on HVAC action
    const getStatusColor = () => {
      switch (hvacAction) {
        case 'heating':
          return '#ff9800';
        case 'cooling':
          return '#2196f3';
        case 'idle':
          return '#4caf50';
        default:
          return '#9e9e9e';
      }
    };

    return html`
      <ha-card>
        <div class="card-header">
          <div class="name">
            ${this.config.title || 'Multizone Climate'}
          </div>
        </div>
        
        <div class="card-content">
          <div class="main-info">
            <div class="temperature-display">
              <div class="current-temp">
                <span class="label">Current</span>
                <span class="value">${formatTemp(currentTemp)}</span>
              </div>
              <div class="target-temp">
                <span class="label">Target</span>
                <span class="value">${formatTemp(targetTemp)}</span>
              </div>
              <div class="outdoor-temp">
                <span class="label">Outdoor</span>
                <span class="value">${formatTemp(outdoorTemp)}</span>
              </div>
            </div>
          </div>

          <div class="status-info">
            <div class="status-item">
              <span class="label">Mode:</span>
              <span class="value" style="color: ${getStatusColor()}">
                ${hvacMode.toUpperCase()}
              </span>
            </div>
            <div class="status-item">
              <span class="label">Action:</span>
              <span class="value" style="color: ${getStatusColor()}">
                ${hvacAction ? hvacAction.toUpperCase() : 'OFF'}
              </span>
            </div>
          </div>

          <div class="zone-info">
            <div class="zone-status">
              <span class="label">Multizone:</span>
              <span class="value ${multizoneEnabled ? 'enabled' : 'disabled'}">
                ${multizoneEnabled ? 'ENABLED' : 'DISABLED'}
              </span>
            </div>
            <div class="zone-count">
              <span class="label">Active Zones:</span>
              <span class="value">${activeZones}</span>
            </div>
          </div>
        </div>
      </ha-card>
    `;
  }

  static styles = css`
    :host {
      display: block;
    }

    ha-card {
      padding: 16px;
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }

    .name {
      font-size: 24px;
      font-weight: 500;
      color: var(--primary-text-color);
    }

    .card-content {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .main-info {
      display: flex;
      flex-direction: column;
    }

    .temperature-display {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
      margin-bottom: 16px;
    }

    .current-temp,
    .target-temp,
    .outdoor-temp {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 12px;
      background: var(--primary-background-color);
      border-radius: 8px;
    }

    .temperature-display .label {
      font-size: 12px;
      color: var(--secondary-text-color);
      margin-bottom: 4px;
    }

    .temperature-display .value {
      font-size: 20px;
      font-weight: 500;
      color: var(--primary-text-color);
    }

    .status-info {
      display: flex;
      justify-content: space-around;
      padding: 12px;
      background: var(--primary-background-color);
      border-radius: 8px;
    }

    .zone-info {
      display: flex;
      justify-content: space-around;
      padding: 12px;
      background: var(--primary-background-color);
      border-radius: 8px;
    }

    .status-item,
    .zone-status,
    .zone-count {
      display: flex;
      gap: 8px;
    }

    .label {
      font-size: 14px;
      color: var(--secondary-text-color);
    }

    .value {
      font-size: 14px;
      font-weight: 500;
      color: var(--primary-text-color);
    }

    .value.enabled {
      color: #4caf50;
    }

    .value.disabled {
      color: #9e9e9e;
    }

    .warning {
      color: var(--error-color);
      padding: 16px;
      text-align: center;
    }
  `;
}

// Register the custom card with Home Assistant
(window as any).customCards = (window as any).customCards || [];
(window as any).customCards.push({
  type: 'multizone-main-climate-card',
  name: 'Multizone Main Climate Card',
  description: 'Card for displaying main climate information',
  preview: false,
});

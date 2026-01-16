/**
 * Dashboard Panel for Multizone Climate.
 * 
 * Displays an overview of all zones with their status:
 * - Zone name
 * - Current and target temperatures
 * - Satisfaction state
 * - Valve state
 * - Temperature direction indicators
 */

import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

interface ZoneConfig {
  entity: string;
  name?: string;
}

@customElement('multizone-dashboard-panel')
export class MultizoneDashboardPanel extends LitElement {
  /**
   * List of zone entities to display.
   */
  @property({ type: Array })
  zones: ZoneConfig[] = [];

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
    if (!config.zones || !Array.isArray(config.zones)) {
      throw new Error('You must specify zones as an array');
    }
    
    this.config = config;
    this.zones = config.zones;
  }

  /**
   * Get satisfaction color based on state.
   */
  getSatisfactionColor(satisfaction: string): string {
    switch (satisfaction) {
      case 'satisfied':
        return '#4caf50';
      case 'underheated':
      case 'undercooled':
        return '#2196f3';
      case 'overheated':
      case 'overcooled':
        return '#f44336';
      default:
        return '#9e9e9e';
    }
  }

  /**
   * Get valve state icon.
   */
  getValveIcon(valveState: string): string {
    return valveState === 'open' ? '🔓' : '🔒';
  }

  /**
   * Get temperature direction indicator.
   */
  getTemperatureDirection(rising: boolean, falling: boolean): string {
    if (rising) return '↑';
    if (falling) return '↓';
    return '→';
  }

  /**
   * Format temperature value.
   */
  formatTemp(temp: number | undefined): string {
    if (temp === undefined || temp === null) return 'N/A';
    return `${temp.toFixed(1)}°C`;
  }

  /**
   * Render a single zone card.
   */
  renderZone(zoneConfig: ZoneConfig) {
    if (!this.hass) return html``;

    const entityState = this.hass.states[zoneConfig.entity];
    if (!entityState) {
      return html`
        <div class="zone-card error">
          <div class="zone-name">${zoneConfig.name || zoneConfig.entity}</div>
          <div class="error-message">Entity not found</div>
        </div>
      `;
    }

    const currentTemp = entityState.attributes.current_temperature;
    const targetTemp = entityState.attributes.temperature;
    const satisfaction = entityState.attributes.satisfaction || 'unknown';
    const valveState = entityState.attributes.valve_state || 'unknown';
    const tempRising = entityState.attributes.temperature_rising || false;
    const tempFalling = entityState.attributes.temperature_falling || false;
    const priority = entityState.attributes.priority || 0;

    const satisfactionColor = this.getSatisfactionColor(satisfaction);
    const valveIcon = this.getValveIcon(valveState);
    const directionIcon = this.getTemperatureDirection(tempRising, tempFalling);

    return html`
      <div class="zone-card">
        <div class="zone-header">
          <div class="zone-name">
            ${zoneConfig.name || entityState.attributes.friendly_name || zoneConfig.entity}
          </div>
          <div class="zone-priority">P${priority}</div>
        </div>
        
        <div class="zone-temps">
          <div class="temp-item">
            <span class="temp-label">Current</span>
            <span class="temp-value">
              ${this.formatTemp(currentTemp)} ${directionIcon}
            </span>
          </div>
          <div class="temp-item">
            <span class="temp-label">Target</span>
            <span class="temp-value">${this.formatTemp(targetTemp)}</span>
          </div>
        </div>

        <div class="zone-status">
          <div class="status-badge" style="background-color: ${satisfactionColor}">
            ${satisfaction.toUpperCase()}
          </div>
          <div class="valve-status">
            ${valveIcon} ${valveState.toUpperCase()}
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Render card HTML.
   */
  render() {
    if (!this.hass) {
      return html`
        <ha-card>
          <div class="card-content">
            <div class="warning">Waiting for Home Assistant...</div>
          </div>
        </ha-card>
      `;
    }

    if (!this.zones || this.zones.length === 0) {
      return html`
        <ha-card>
          <div class="card-content">
            <div class="warning">No zones configured</div>
          </div>
        </ha-card>
      `;
    }

    return html`
      <ha-card>
        <div class="card-header">
          <div class="panel-title">
            ${this.config.title || 'Multizone Climate Dashboard'}
          </div>
        </div>
        
        <div class="card-content">
          <div class="zones-grid">
            ${this.zones.map(zone => this.renderZone(zone))}
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
      margin-bottom: 16px;
    }

    .panel-title {
      font-size: 24px;
      font-weight: 500;
      color: var(--primary-text-color);
    }

    .zones-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
    }

    .zone-card {
      background: var(--primary-background-color);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .zone-card.error {
      border: 2px solid var(--error-color);
    }

    .zone-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    .zone-name {
      font-size: 16px;
      font-weight: 500;
      color: var(--primary-text-color);
    }

    .zone-priority {
      font-size: 12px;
      padding: 2px 8px;
      background: var(--secondary-background-color);
      border-radius: 12px;
      color: var(--secondary-text-color);
    }

    .zone-temps {
      display: flex;
      justify-content: space-between;
      margin-bottom: 12px;
    }

    .temp-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .temp-label {
      font-size: 12px;
      color: var(--secondary-text-color);
    }

    .temp-value {
      font-size: 18px;
      font-weight: 500;
      color: var(--primary-text-color);
    }

    .zone-status {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .status-badge {
      padding: 4px 12px;
      border-radius: 16px;
      font-size: 12px;
      font-weight: 500;
      color: white;
    }

    .valve-status {
      font-size: 14px;
      color: var(--secondary-text-color);
    }

    .warning,
    .error-message {
      color: var(--error-color);
      padding: 16px;
      text-align: center;
    }
  `;
}

// Register the custom card with Home Assistant
(window as any).customCards = (window as any).customCards || [];
(window as any).customCards.push({
  type: 'multizone-dashboard-panel',
  name: 'Multizone Dashboard Panel',
  description: 'Dashboard panel showing all zones',
  preview: false,
});

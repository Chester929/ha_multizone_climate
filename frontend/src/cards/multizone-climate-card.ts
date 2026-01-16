/**
 * Multizone Climate Card for Home Assistant.
 * 
 * Displays zone information:
 * - Zone name
 * - Current temperature
 * - Target temperature
 * - Satisfaction state
 * - Valve state
 * - Temperature direction
 */

import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('multizone-climate-card')
export class MultizoneClimateCard extends LitElement {
  /**
   * Entity ID for the zone climate entity.
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
            <div class="warning">Entity "${this.entity}" not found</div>
          </div>
        </ha-card>
      `;
    }

    // Extract zone information
    const zoneName = entityState.attributes.friendly_name || 'Unknown Zone';
    const currentTemp = entityState.attributes.current_temperature;
    const targetTemp = entityState.attributes.temperature;
    const satisfaction = entityState.attributes.satisfaction || 'unknown';
    const valveState = entityState.attributes.valve_state || 'unknown';
    const tempRising = entityState.attributes.temperature_rising;
    const tempFalling = entityState.attributes.temperature_falling;
    
    // Determine temperature direction
    let tempDirection = '—';
    if (tempRising) {
      tempDirection = '↑';
    } else if (tempFalling) {
      tempDirection = '↓';
    }
    
    // Get satisfaction badge class
    const satisfactionClass = this.getSatisfactionClass(satisfaction);
    
    return html`
      <ha-card>
        <div class="card-content">
          <div class="zone-header">
            <div class="zone-name">${zoneName}</div>
            <div class="satisfaction-badge ${satisfactionClass}">${satisfaction}</div>
          </div>
          
          <div class="temperature-display">
            <div class="current-temp">
              <span class="temp-value">${currentTemp?.toFixed(1) || '--'}</span>
              <span class="temp-unit">°C</span>
              <span class="temp-direction">${tempDirection}</span>
            </div>
            <div class="target-temp">
              <span class="label">Target:</span>
              <span class="temp-value">${targetTemp?.toFixed(1) || '--'}</span>
              <span class="temp-unit">°C</span>
            </div>
          </div>
          
          <div class="controls">
            <button class="temp-button" @click=${() => this.adjustTemperature(-0.5)}>
              <span>−</span>
            </button>
            <div class="target-value">${targetTemp?.toFixed(1) || '--'}°C</div>
            <button class="temp-button" @click=${() => this.adjustTemperature(0.5)}>
              <span>+</span>
            </button>
          </div>
          
          <div class="status-row">
            <div class="valve-state">
              <span class="label">Valve:</span>
              <span class="value ${valveState}">${valveState}</span>
            </div>
          </div>
        </div>
      </ha-card>
    `;
  }
  
  /**
   * Get CSS class for satisfaction badge.
   */
  private getSatisfactionClass(satisfaction: string): string {
    switch (satisfaction) {
      case 'satisfied':
        return 'satisfied';
      case 'underheated':
      case 'undercooled':
        return 'needs-heat';
      case 'overheated':
      case 'overcooled':
        return 'needs-cool';
      default:
        return 'unknown';
    }
  }
  
  /**
   * Adjust target temperature.
   */
  private adjustTemperature(delta: number): void {
    if (!this.hass || !this.entity) return;
    
    const entityState = this.hass.states[this.entity];
    if (!entityState) return;
    
    const currentTarget = entityState.attributes.temperature || 20;
    const newTarget = Math.round((currentTarget + delta) * 2) / 2; // Round to 0.5
    
    // Call Home Assistant service to set temperature
    this.hass.callService('climate', 'set_temperature', {
      entity_id: this.entity,
      temperature: newTarget,
    });
  }

  /**
   * Card styles.
   */
  static get styles() {
    return css`
      :host {
        display: block;
      }
      
      .card-content {
        padding: 16px;
      }
      
      .warning {
        color: var(--error-color);
        font-weight: bold;
        padding: 8px;
        text-align: center;
      }
      
      .zone-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
      }
      
      .zone-name {
        font-size: 1.3em;
        font-weight: 500;
        color: var(--primary-text-color);
      }
      
      .satisfaction-badge {
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85em;
        font-weight: 500;
        text-transform: capitalize;
      }
      
      .satisfaction-badge.satisfied {
        background-color: var(--success-color, #4caf50);
        color: white;
      }
      
      .satisfaction-badge.needs-heat {
        background-color: var(--warning-color, #ff9800);
        color: white;
      }
      
      .satisfaction-badge.needs-cool {
        background-color: var(--info-color, #2196f3);
        color: white;
      }
      
      .satisfaction-badge.unknown {
        background-color: var(--disabled-color, #bdbdbd);
        color: white;
      }
      
      .temperature-display {
        text-align: center;
        margin: 20px 0;
      }
      
      .current-temp {
        font-size: 3em;
        font-weight: 300;
        color: var(--primary-text-color);
        display: flex;
        align-items: baseline;
        justify-content: center;
        gap: 4px;
      }
      
      .current-temp .temp-unit {
        font-size: 0.5em;
        color: var(--secondary-text-color);
      }
      
      .current-temp .temp-direction {
        font-size: 0.6em;
        color: var(--secondary-text-color);
        margin-left: 8px;
      }
      
      .target-temp {
        font-size: 1em;
        color: var(--secondary-text-color);
        margin-top: 8px;
      }
      
      .target-temp .label {
        margin-right: 4px;
      }
      
      .controls {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 16px;
        margin: 20px 0;
      }
      
      .temp-button {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        border: 2px solid var(--primary-color);
        background-color: var(--card-background-color);
        color: var(--primary-color);
        font-size: 1.5em;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
      }
      
      .temp-button:hover {
        background-color: var(--primary-color);
        color: white;
      }
      
      .temp-button:active {
        transform: scale(0.95);
      }
      
      .target-value {
        font-size: 1.5em;
        font-weight: 500;
        min-width: 80px;
        text-align: center;
        color: var(--primary-text-color);
      }
      
      .status-row {
        display: flex;
        justify-content: space-around;
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid var(--divider-color);
      }
      
      .valve-state,
      .priority-indicator {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      
      .label {
        color: var(--secondary-text-color);
        font-size: 0.9em;
      }
      
      .value {
        font-weight: 500;
        text-transform: capitalize;
      }
      
      .value.open {
        color: var(--success-color, #4caf50);
      }
      
      .value.closed {
        color: var(--disabled-color, #bdbdbd);
      }
      
      .value.opening,
      .value.closing {
        color: var(--warning-color, #ff9800);
      }
    `;
  }
}

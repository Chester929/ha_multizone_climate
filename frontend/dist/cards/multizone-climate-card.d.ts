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
import { LitElement } from 'lit';
export declare class MultizoneClimateCard extends LitElement {
    /**
     * Entity ID for the zone climate entity.
     */
    entity?: string;
    /**
     * Card configuration from Lovelace UI editor.
     */
    config?: any;
    /**
     * Home Assistant instance.
     */
    hass?: any;
    /**
     * Set configuration from Lovelace editor.
     *
     * @param config - Card configuration
     */
    setConfig(config: any): void;
    /**
     * Render card HTML.
     *
     * Returns:
     *   Card HTML template
     */
    render(): import("lit-html").TemplateResult<1>;
    /**
     * Get CSS class for satisfaction badge.
     */
    private getSatisfactionClass;
    /**
     * Adjust target temperature.
     */
    private adjustTemperature;
    /**
     * Card styles.
     */
    static get styles(): import("lit").CSSResult;
}

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
import { LitElement } from 'lit';
export declare class MultizoneMainClimateCard extends LitElement {
    /**
     * Entity ID for the main climate entity.
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
    static styles: import("lit").CSSResult;
}

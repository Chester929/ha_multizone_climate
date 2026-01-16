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
import { LitElement } from 'lit';
interface ZoneConfig {
    entity: string;
    name?: string;
}
export declare class MultizoneDashboardPanel extends LitElement {
    /**
     * List of zone entities to display.
     */
    zones: ZoneConfig[];
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
     * Get satisfaction color based on state.
     */
    getSatisfactionColor(satisfaction: string): string;
    /**
     * Get valve state icon.
     */
    getValveIcon(valveState: string): string;
    /**
     * Get temperature direction indicator.
     */
    getTemperatureDirection(rising: boolean, falling: boolean): string;
    /**
     * Format temperature value.
     */
    formatTemp(temp: number | undefined): string;
    /**
     * Render a single zone card.
     */
    renderZone(zoneConfig: ZoneConfig): import("lit-html").TemplateResult<1>;
    /**
     * Render card HTML.
     */
    render(): import("lit-html").TemplateResult<1>;
    static styles: import("lit").CSSResult;
}
export {};

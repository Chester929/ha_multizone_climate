import React, { useState, useEffect, useCallback } from 'react';
import { Config } from '../types';

// Whitelist of allowed configuration keys
const ALLOWED_CONFIG_KEYS = [
  'main_climate_entity_id',
  'main_target_all_zones_satisfied',
  'use_average_mode',
  'slider_position',
  'min_valves_open',
  'main_min_temp',
  'main_max_temp',
  'main_change_threshold',
  'valve_actuation_delay',
  'coordinator_interval',
  'satisfaction_eps',
];

// Helper to check if a string represents a finite numeric value
function isNumericString(value: string): boolean {
  const trimmed = value.trim();
  if (trimmed === '') {
    return false;
  }
  const num = Number(trimmed);
  return Number.isFinite(num);
}

function isValidConfig(data: unknown): data is Config {
  if (typeof data !== 'object' || data === null) {
    return false;
  }
  
  const entries = Object.entries(data as Record<string, unknown>);
  
  // Check if all keys are in the whitelist and values are meaningful
  for (const [key, value] of entries) {
    if (!ALLOWED_CONFIG_KEYS.includes(key)) {
      return false;
    }
    
    // Allow undefined values to represent "not set"
    if (value === undefined) {
      continue;
    }
    
    if (typeof value !== 'string') {
      return false;
    }
    
    const strValue = value.trim();
    
    // Validate based on key type
    switch (key) {
      case 'main_climate_entity_id':
        // Allow empty string as "not set"; otherwise entity ID must match format: domain.entity_name
        if (strValue !== '' && !/^[a-z_]+\.[a-z0-9_]+$/.test(strValue)) {
          return false;
        }
        break;
      case 'main_target_all_zones_satisfied':
      case 'slider_position':
      case 'main_change_threshold':
      case 'satisfaction_eps':
      case 'main_min_temp':
      case 'main_max_temp':
        // These configuration values must be numeric strings
        if (!isNumericString(strValue)) {
          return false;
        }
        break;
      case 'use_average_mode':
        // Boolean fields should be "true" or "false"
        if (strValue !== 'true' && strValue !== 'false') {
          return false;
        }
        break;
      case 'min_valves_open':
      case 'valve_actuation_delay':
      case 'coordinator_interval':
        // Integer fields must be numeric
        if (!isNumericString(strValue)) {
          return false;
        }
        break;
      default:
        // Should not be reachable due to the whitelist check
        break;
    }
  }
  
  return true;
}

export function ConfigManager() {
  const [config, setConfig] = useState<Config>({});
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editedConfig, setEditedConfig] = useState<Config>({});

  const fetchConfig = useCallback(async () => {
    try {
      const response = await fetch('/api/config');
      const data = await response.json();
      setConfig(data);
      setEditedConfig(data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching config:', error);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSave = async () => {
    try {
      const response = await fetch('/api/config', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(editedConfig),
      });

      if (response.ok) {
        setConfig(editedConfig);
        setEditing(false);
      } else {
        alert('Failed to save configuration');
      }
    } catch (error) {
      console.error('Error saving config:', error);
      alert('Failed to save configuration');
    }
  };

  const handleExport = () => {
    const dataStr = JSON.stringify(config, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    const exportFileDefaultName = `multizone-config-${new Date().toISOString()}.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const handleImport = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const imported = JSON.parse(e.target?.result as string);
        
        // Validate the imported configuration
        if (!isValidConfig(imported)) {
          alert('Invalid configuration file: Must contain only allowed keys with string values. Allowed keys: ' + ALLOWED_CONFIG_KEYS.join(', '));
          return;
        }
        
        setEditedConfig(imported);
        setEditing(true);
      } catch (error) {
        alert('Invalid configuration file: Unable to parse JSON');
      }
    };
    reader.readAsText(file);
  };

  if (loading) {
    return <div className="loading">Loading configuration...</div>;
  }

  return (
    <div className="config-manager">
      <div className="config-header">
        <h2>System Configuration</h2>
        <div className="config-actions">
          <button onClick={handleExport} className="btn btn-secondary">
            Export Config
          </button>
          <label className="btn btn-secondary">
            Import Config
            <input
              type="file"
              accept=".json"
              onChange={handleImport}
              style={{ display: 'none' }}
            />
          </label>
        </div>
      </div>

      <div className="config-content">
        <h3>Main Climate Entity</h3>
        <div className="config-item">
          <label>Main Climate Entity ID</label>
          {editing ? (
            <>
              <input
                type="text"
                placeholder="climate.main_thermostat"
                pattern="^[a-z_]+\.[a-z0-9_]+$"
                title="Format: domain.entity_name (e.g., climate.thermostat)"
                value={editedConfig.main_climate_entity_id || ''}
                onChange={(e) =>
                  setEditedConfig({ ...editedConfig, main_climate_entity_id: e.target.value })
                }
              />
              <small>Home Assistant entity ID for the main HVAC climate control</small>
            </>
          ) : (
            <span>{config.main_climate_entity_id || 'Not set'}</span>
          )}
        </div>

        <h3 style={{ marginTop: '1.5rem' }}>Temperature Calculation Settings</h3>
        
        <div className="config-item">
          <label>Calculation Mode</label>
          {editing ? (
            <>
              <select
                value={editedConfig.use_average_mode || 'false'}
                onChange={(e) => setEditedConfig({ ...editedConfig, use_average_mode: e.target.value })}
              >
                <option value="false">Slider Mode</option>
                <option value="true">Average Mode</option>
              </select>
              <small>Average: mean of all zones. Slider: interpolate between min/max targets</small>
            </>
          ) : (
            <span>{config.use_average_mode === 'true' ? 'Average Mode' : 'Slider Mode'}</span>
          )}
        </div>

        {editing && editedConfig.use_average_mode === 'false' && (
          <div className="config-item">
            <label>Slider Position (0.0 - 1.0)</label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="1"
              value={editedConfig.slider_position || '0.5'}
              onChange={(e) =>
                setEditedConfig({ ...editedConfig, slider_position: e.target.value })
              }
            />
            <small>Position between minimum and maximum zone targets (0=min, 1=max)</small>
          </div>
        )}

        <div className="config-item">
          <label>Main Target (All Zones Satisfied) °C</label>
          {editing ? (
            <>
              <input
                type="number"
                step="0.5"
                min="5"
                max="35"
                value={editedConfig.main_target_all_zones_satisfied || ''}
                onChange={(e) =>
                  setEditedConfig({ ...editedConfig, main_target_all_zones_satisfied: e.target.value })
                }
              />
              <small>Target temperature when all zones are satisfied</small>
            </>
          ) : (
            <span>{config.main_target_all_zones_satisfied || 'Not set'}</span>
          )}
        </div>

        <div className="config-item">
          <label>Main Change Threshold °C</label>
          {editing ? (
            <>
              <input
                type="number"
                step="0.1"
                min="0.1"
                max="5"
                value={editedConfig.main_change_threshold || '0.5'}
                onChange={(e) =>
                  setEditedConfig({ ...editedConfig, main_change_threshold: e.target.value })
                }
              />
              <small>Minimum temperature change to update main thermostat</small>
            </>
          ) : (
            <span>{config.main_change_threshold || 'Not set'}</span>
          )}
        </div>

        <h3 style={{ marginTop: '1.5rem' }}>Temperature Limits</h3>

        <div className="config-item">
          <label>Main Minimum Temperature °C</label>
          {editing ? (
            <input
              type="number"
              step="0.5"
              min="5"
              max="35"
              value={editedConfig.main_min_temp || ''}
              onChange={(e) =>
                setEditedConfig({ ...editedConfig, main_min_temp: e.target.value })
              }
            />
          ) : (
            <span>{config.main_min_temp || 'Not set'}</span>
          )}
        </div>

        <div className="config-item">
          <label>Main Maximum Temperature °C</label>
          {editing ? (
            <input
              type="number"
              step="0.5"
              min="5"
              max="90"
              value={editedConfig.main_max_temp || ''}
              onChange={(e) =>
                setEditedConfig({ ...editedConfig, main_max_temp: e.target.value })
              }
            />
          ) : (
            <span>{config.main_max_temp || 'Not set'}</span>
          )}
        </div>

        <h3 style={{ marginTop: '1.5rem' }}>Valve Management</h3>

        <div className="config-item">
          <label>Minimum Valves Open</label>
          {editing ? (
            <>
              <input
                type="number"
                min="0"
                max="10"
                value={editedConfig.min_valves_open || '1'}
                onChange={(e) =>
                  setEditedConfig({ ...editedConfig, min_valves_open: e.target.value })
                }
              />
              <small>Minimum number of valves to keep open (safety feature)</small>
            </>
          ) : (
            <span>{config.min_valves_open || 'Not set'}</span>
          )}
        </div>

        <div className="config-item">
          <label>Valve Actuation Delay (seconds)</label>
          {editing ? (
            <>
              <input
                type="number"
                min="30"
                max="600"
                value={editedConfig.valve_actuation_delay || '120'}
                onChange={(e) =>
                  setEditedConfig({ ...editedConfig, valve_actuation_delay: e.target.value })
                }
              />
              <small>Cooldown period between valve state changes</small>
            </>
          ) : (
            <span>{config.valve_actuation_delay || 'Not set'}</span>
          )}
        </div>

        <h3 style={{ marginTop: '1.5rem' }}>Advanced Settings</h3>

        <div className="config-item">
          <label>Coordinator Interval (seconds)</label>
          {editing ? (
            <>
              <input
                type="number"
                min="5"
                max="300"
                value={editedConfig.coordinator_interval || '15'}
                onChange={(e) =>
                  setEditedConfig({ ...editedConfig, coordinator_interval: e.target.value })
                }
              />
              <small>How often to recalculate and update system state</small>
            </>
          ) : (
            <span>{config.coordinator_interval || 'Not set'}</span>
          )}
        </div>

        <div className="config-item">
          <label>Satisfaction Epsilon °C</label>
          {editing ? (
            <>
              <input
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={editedConfig.satisfaction_eps || '0'}
                onChange={(e) =>
                  setEditedConfig({ ...editedConfig, satisfaction_eps: e.target.value })
                }
              />
              <small>Additional tolerance for satisfaction calculation (0 = exact)</small>
            </>
          ) : (
            <span>{config.satisfaction_eps || 'Not set'}</span>
          )}
        </div>
      </div>

      <div className="config-controls">
        {editing ? (
          <>
            <button onClick={handleSave} className="btn btn-primary">
              Save Configuration
            </button>
            <button
              onClick={() => {
                setEditedConfig(config);
                setEditing(false);
              }}
              className="btn btn-secondary"
            >
              Cancel
            </button>
          </>
        ) : (
          <button onClick={() => setEditing(true)} className="btn btn-primary">
            Edit Configuration
          </button>
        )}
      </div>
    </div>
  );
}

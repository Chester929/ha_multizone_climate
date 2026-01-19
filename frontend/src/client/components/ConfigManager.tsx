import React, { useState, useEffect, useCallback } from 'react';
import { Config } from '../types';

// Whitelist of allowed configuration keys
const ALLOWED_CONFIG_KEYS = [
  'main_target_temperature',
  'mode',
  'hysteresis',
  'min_temperature',
  'max_temperature',
  'update_interval',
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
      case 'main_target_temperature':
      case 'hysteresis':
      case 'min_temperature':
      case 'max_temperature':
      case 'update_interval':
        // These configuration values must be numeric strings
        if (!isNumericString(strValue)) {
          return false;
        }
        break;
      case 'mode':
        // Mode must be a non-empty string
        if (strValue.length === 0) {
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
        <div className="config-item">
          <label>Main Target Temperature (°C)</label>
          {editing ? (
            <input
              type="number"
              step="0.5"
              value={editedConfig.main_target_temperature || ''}
              onChange={(e) =>
                setEditedConfig({ ...editedConfig, main_target_temperature: e.target.value })
              }
            />
          ) : (
            <span>{config.main_target_temperature || 'Not set'}</span>
          )}
        </div>

        <div className="config-item">
          <label>Mode</label>
          {editing ? (
            <select
              value={editedConfig.mode || ''}
              onChange={(e) => setEditedConfig({ ...editedConfig, mode: e.target.value })}
            >
              <option value="">Select mode</option>
              <option value="heating">Heating</option>
              <option value="cooling">Cooling</option>
              <option value="auto">Auto</option>
            </select>
          ) : (
            <span>{config.mode || 'Not set'}</span>
          )}
        </div>

        {Object.entries(editing ? editedConfig : config)
          .filter(([key]) => key !== 'main_target_temperature' && key !== 'mode')
          .map(([key, value]) => (
            <div key={key} className="config-item">
              <label>{key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}</label>
              {editing ? (
                <input
                  type="text"
                  value={value || ''}
                  onChange={(e) =>
                    setEditedConfig({ ...editedConfig, [key]: e.target.value })
                  }
                />
              ) : (
                <span>{value || 'Not set'}</span>
              )}
            </div>
          ))}
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

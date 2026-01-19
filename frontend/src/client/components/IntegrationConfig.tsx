import React, { useState, useEffect, useCallback } from 'react';

interface IntegrationSettings {
  // Home Assistant
  ha_enabled?: string;
  ha_base_url?: string;
  ha_token?: string;
  ha_websocket?: string;
  
  // MQTT
  mqtt_enabled?: string;
  mqtt_broker?: string;
  mqtt_port?: string;
  mqtt_username?: string;
  mqtt_password?: string;
}

export function IntegrationConfig() {
  const [settings, setSettings] = useState<IntegrationSettings>({});
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editedSettings, setEditedSettings] = useState<IntegrationSettings>({});
  const [testResult, setTestResult] = useState<{ type: 'success' | 'error', message: string } | null>(null);

  const fetchSettings = useCallback(async () => {
    try {
      const response = await fetch('/api/integrations');
      const data = await response.json();
      setSettings(data);
      setEditedSettings(data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching integration settings:', error);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  // Auto-clear success messages after 3 seconds
  useEffect(() => {
    if (testResult && testResult.type === 'success') {
      const timeoutId = setTimeout(() => setTestResult(null), 3000);
      return () => clearTimeout(timeoutId);
    }
  }, [testResult]);

  const handleSave = async () => {
    try {
      const response = await fetch('/api/integrations', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(editedSettings),
      });

      if (response.ok) {
        setSettings(editedSettings);
        setEditing(false);
        setTestResult({ type: 'success', message: 'Integration settings saved successfully!' });
      } else {
        setTestResult({ type: 'error', message: 'Failed to save integration settings' });
      }
    } catch (error) {
      console.error('Error saving settings:', error);
      setTestResult({ type: 'error', message: 'Failed to save integration settings' });
    }
  };

  const handleTestHA = async () => {
    setTestResult(null);
    
    // Validate that settings are configured
    if (!editedSettings.ha_base_url || !editedSettings.ha_token) {
      setTestResult({ type: 'error', message: 'Please configure and save HA settings before testing.' });
      return;
    }
    
    if (editing) {
      setTestResult({ type: 'error', message: 'Please save settings before testing the connection.' });
      return;
    }
    
    try {
      const response = await fetch('/api/ha/test');
      
      if (!response.ok) {
        if (response.status === 404) {
          setTestResult({ type: 'error', message: 'Test endpoint not available. This feature requires the logic container to be configured with HA integration enabled.' });
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.connected) {
        setTestResult({ type: 'success', message: 'Home Assistant connection successful!' });
      } else {
        setTestResult({ type: 'error', message: `Connection failed: ${data.error || 'Unknown error'}` });
      }
    } catch (error) {
      setTestResult({ type: 'error', message: 'Test connection feature requires the logic container to be running with HA integration enabled.' });
    }
  };

  if (loading) {
    return <div className="loading">Loading integration settings...</div>;
  }

  const haEnabled = editedSettings.ha_enabled === 'true';
  const mqttEnabled = editedSettings.mqtt_enabled === 'true';

  return (
    <div className="integration-config">
      {testResult && (
        <div className={`alert ${testResult.type === 'success' ? 'alert-success' : 'alert-error'}`}>
          {testResult.message}
        </div>
      )}

      {/* Home Assistant Section */}
      <div className="integration-section">
        <div className="integration-header">
          <h3>🏠 Home Assistant Integration</h3>
          <label className="toggle-switch">
            <input
              type="checkbox"
              checked={haEnabled}
              onChange={(e) => setEditedSettings({ ...editedSettings, ha_enabled: e.target.checked ? 'true' : 'false' })}
              disabled={!editing}
            />
            <span className="toggle-slider"></span>
          </label>
        </div>

        {haEnabled && (
          <div className="integration-fields">
            <div className="config-item">
              <label>Base URL</label>
              {editing ? (
                <input
                  type="text"
                  value={editedSettings.ha_base_url || ''}
                  onChange={(e) => setEditedSettings({ ...editedSettings, ha_base_url: e.target.value })}
                  placeholder="http://homeassistant.local:8123"
                />
              ) : (
                <span>{settings.ha_base_url || 'Not set'}</span>
              )}
            </div>

            <div className="config-item">
              <label>Access Token</label>
              {editing ? (
                <input
                  type="password"
                  value={editedSettings.ha_token || ''}
                  onChange={(e) => setEditedSettings({ ...editedSettings, ha_token: e.target.value })}
                  placeholder="your_long_lived_access_token"
                />
              ) : (
                <span>{settings.ha_token ? '••••••••••••' : 'Not set'}</span>
              )}
            </div>

            <div className="config-item">
              <label>WebSocket Enabled</label>
              {editing ? (
                <select
                  value={editedSettings.ha_websocket || 'true'}
                  onChange={(e) => setEditedSettings({ ...editedSettings, ha_websocket: e.target.value })}
                >
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              ) : (
                <span>{settings.ha_websocket === 'true' ? 'Yes' : 'No'}</span>
              )}
            </div>

            {!editing && (
              <div className="config-item">
                <button onClick={handleTestHA} className="btn btn-secondary">
                  Test Connection
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* MQTT Section */}
      <div className="integration-section">
        <div className="integration-header">
          <h3>📡 MQTT Integration</h3>
          <label className="toggle-switch">
            <input
              type="checkbox"
              checked={mqttEnabled}
              onChange={(e) => setEditedSettings({ ...editedSettings, mqtt_enabled: e.target.checked ? 'true' : 'false' })}
              disabled={!editing}
            />
            <span className="toggle-slider"></span>
          </label>
        </div>

        {mqttEnabled && (
          <div className="integration-fields">
            <div className="config-item">
              <label>Broker</label>
              {editing ? (
                <input
                  type="text"
                  value={editedSettings.mqtt_broker || ''}
                  onChange={(e) => setEditedSettings({ ...editedSettings, mqtt_broker: e.target.value })}
                  placeholder="homeassistant.local"
                />
              ) : (
                <span>{settings.mqtt_broker || 'Not set'}</span>
              )}
            </div>

            <div className="config-item">
              <label>Port</label>
              {editing ? (
                <input
                  type="number"
                  value={editedSettings.mqtt_port || ''}
                  onChange={(e) => setEditedSettings({ ...editedSettings, mqtt_port: e.target.value })}
                  placeholder="1883"
                />
              ) : (
                <span>{settings.mqtt_port || 'Not set'}</span>
              )}
            </div>

            <div className="config-item">
              <label>Username</label>
              {editing ? (
                <input
                  type="text"
                  value={editedSettings.mqtt_username || ''}
                  onChange={(e) => setEditedSettings({ ...editedSettings, mqtt_username: e.target.value })}
                  placeholder="mqtt_user"
                />
              ) : (
                <span>{settings.mqtt_username || 'Not set'}</span>
              )}
            </div>

            <div className="config-item">
              <label>Password</label>
              {editing ? (
                <input
                  type="password"
                  value={editedSettings.mqtt_password || ''}
                  onChange={(e) => setEditedSettings({ ...editedSettings, mqtt_password: e.target.value })}
                  placeholder="mqtt_password"
                />
              ) : (
                <span>{settings.mqtt_password ? '••••••••••••' : 'Not set'}</span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="config-controls">
        {editing ? (
          <>
            <button onClick={handleSave} className="btn btn-primary">
              Save Integration Settings
            </button>
            <button
              onClick={() => {
                setEditedSettings(settings);
                setEditing(false);
                setTestResult(null);
              }}
              className="btn btn-secondary"
            >
              Cancel
            </button>
          </>
        ) : (
          <button onClick={() => setEditing(true)} className="btn btn-primary">
            Edit Integration Settings
          </button>
        )}
      </div>
    </div>
  );
}

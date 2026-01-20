import React, { useState, useEffect, useCallback } from 'react';
import { Zone, SystemStatus } from '../types';
import { useWebSocket } from '../hooks/useWebSocket';
import { ZoneCard } from './ZoneCard';
import { ConfigManager } from './ConfigManager';
import { IntegrationConfig } from './IntegrationConfig';
import './App.css';

interface ZoneResponse {
  id?: string;
  name?: string;
  enabled?: string | boolean;
  current_temperature?: string;
  target_temperature?: string;
  satisfaction?: string;
  valve_state?: string;
  priority?: number;
}

export function App() {
  const [zones, setZones] = useState<Zone[]>([]);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'zones' | 'config' | 'integrations'>('zones');
  const [showAddZone, setShowAddZone] = useState(false);
  const { connected, lastMessage } = useWebSocket('/ws');

  const fetchZones = useCallback(async () => {
    try {
      const response = await fetch('/api/zones');
      const data: ZoneResponse[] = await response.json();
      const parsedZones: Zone[] = data.map((z) => ({
        id: z.id || '',
        name: z.name || '',
        enabled: z.enabled === 'true' || z.enabled === true,
        current_temperature: z.current_temperature,
        target_temperature: z.target_temperature,
        satisfaction: z.satisfaction,
        valve_state: z.valve_state,
        priority: z.priority,
      }));
      setZones(parsedZones);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching zones:', error);
      setLoading(false);
    }
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch('/health');
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      console.error('Error fetching status:', error);
    }
  }, []);

  useEffect(() => {
    fetchZones();
    fetchStatus();
  }, [fetchZones, fetchStatus]);

  useEffect(() => {
    if (lastMessage) {
      // Refresh zones on updates
      if (lastMessage.type.includes('zone')) {
        fetchZones();
      }
    }
  }, [lastMessage, fetchZones]);

  const handleUpdateZone = async (zone: Zone) => {
    try {
      const response = await fetch(`/api/zones/${zone.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...zone,
          enabled: zone.enabled.toString(),
          priority: zone.priority?.toString(),
        }),
      });

      if (response.ok) {
        fetchZones();
        fetchStatus();
      } else {
        alert('Failed to update zone');
      }
    } catch (error) {
      console.error('Error updating zone:', error);
      alert('Failed to update zone');
    }
  };

  const handleDeleteZone = async (id: string) => {
    // Validate zone ID exists
    if (!id || id.trim() === '') {
      alert('Invalid zone ID');
      return;
    }

    try {
      const response = await fetch(`/api/zones/${id}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        fetchZones();
        fetchStatus();
      } else {
        alert('Failed to delete zone');
      }
    } catch (error) {
      console.error('Error deleting zone:', error);
      alert('Failed to delete zone');
    }
  };

  const handleAddZone = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    
    const newZone: Record<string, string> = {
      name: formData.get('name') as string,
      enabled: 'true',
      target_temperature: formData.get('target_temperature') as string,
      priority: (formData.get('priority') as string) || '0',
    };

    // Add optional ID if provided
    const zoneId = formData.get('id') as string;
    if (zoneId && zoneId.trim() !== '') {
      newZone.id = zoneId.trim();
    }

    // Add optional HA entity IDs if provided
    const tempSensor = formData.get('temperature_sensor_entity_id') as string;
    if (tempSensor && tempSensor.trim() !== '') {
      newZone.temperature_sensor_entity_id = tempSensor.trim();
    }

    const valveSwitch = formData.get('valve_switch_entity_id') as string;
    if (valveSwitch && valveSwitch.trim() !== '') {
      newZone.valve_switch_entity_id = valveSwitch.trim();
    }

    const climateEntity = formData.get('climate_entity_id') as string;
    if (climateEntity && climateEntity.trim() !== '') {
      newZone.climate_entity_id = climateEntity.trim();
    }

    try {
      const response = await fetch('/api/zones', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newZone),
      });

      if (response.ok) {
        setShowAddZone(false);
        fetchZones();
        event.currentTarget.reset();
      } else {
        const errorData = await response.json();
        alert(`Failed to create zone: ${errorData.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error creating zone:', error);
      alert('Failed to create zone: Network error');
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>🌡️ Multizone Climate Control</h1>
          <p className="subtitle">Advanced Multi-Zone HVAC Management System v2.0</p>
        </div>
        <div className="header-status">
          <span className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? '● Live' : '○ Offline'}
          </span>
          <span className="system-status">
            {status?.status || 'Unknown'}
          </span>
        </div>
      </header>

      <nav className="app-nav">
        <button
          className={`nav-button ${activeTab === 'zones' ? 'active' : ''}`}
          onClick={() => setActiveTab('zones')}
        >
          Zones ({zones.length})
        </button>
        <button
          className={`nav-button ${activeTab === 'config' ? 'active' : ''}`}
          onClick={() => setActiveTab('config')}
        >
          Configuration
        </button>
        <button
          className={`nav-button ${activeTab === 'integrations' ? 'active' : ''}`}
          onClick={() => setActiveTab('integrations')}
        >
          Integrations
        </button>
      </nav>

      <main className="app-main">
        {activeTab === 'zones' && (
          <div className="zones-section">
            <div className="section-header">
              <h2>Zones</h2>
              <button
                onClick={() => setShowAddZone(!showAddZone)}
                className="btn btn-primary"
              >
                {showAddZone ? 'Cancel' : '+ Add Zone'}
              </button>
            </div>

            {showAddZone && (
              <form onSubmit={handleAddZone} className="add-zone-form">
                <div className="form-group">
                  <label>Zone ID</label>
                  <input type="text" name="id" placeholder="zone-living-room" pattern="[a-zA-Z0-9_-]+" title="Only alphanumeric characters, hyphens, and underscores allowed" />
                  <small>Optional - will be auto-generated if not provided</small>
                </div>
                <div className="form-group">
                  <label>Zone Name</label>
                  <input type="text" name="name" required placeholder="Living Room" />
                </div>
                <div className="form-group">
                  <label>Target Temperature (°C)</label>
                  <input type="number" name="target_temperature" step="0.5" min="-50" max="100" defaultValue="20" required />
                </div>
                <div className="form-group">
                  <label>Priority (0-100)</label>
                  <input type="number" name="priority" min="0" max="100" defaultValue="0" />
                </div>
                
                <h4 style={{ marginTop: '1.5rem', marginBottom: '0.5rem' }}>Home Assistant Integration (Optional)</h4>
                <div className="form-group">
                  <label>Temperature Sensor Entity ID</label>
                  <input type="text" name="temperature_sensor_entity_id" placeholder="sensor.living_room_temperature" pattern="^[a-z_]+\.[a-z0-9_]+$" title="Format: domain.entity_name (e.g., sensor.temperature)" />
                  <small>Entity ID of the temperature sensor</small>
                </div>
                <div className="form-group">
                  <label>Valve Switch Entity ID</label>
                  <input type="text" name="valve_switch_entity_id" placeholder="switch.living_room_valve" pattern="^[a-z_]+\.[a-z0-9_]+$" title="Format: domain.entity_name (e.g., switch.valve)" />
                  <small>Entity ID of the valve control switch</small>
                </div>
                <div className="form-group">
                  <label>Climate Entity ID</label>
                  <input type="text" name="climate_entity_id" placeholder="climate.living_room" pattern="^[a-z_]+\.[a-z0-9_]+$" title="Format: domain.entity_name (e.g., climate.zone)" />
                  <small>Optional: Link to existing HA climate entity to sync temperature and valve state</small>
                </div>
                
                <button type="submit" className="btn btn-primary">Create Zone</button>
              </form>
            )}

            {loading ? (
              <div className="loading">Loading zones...</div>
            ) : zones.length === 0 ? (
              <div className="no-data">
                No zones configured yet. Click "Add Zone" to create one.
              </div>
            ) : (
              <div className="zones-grid">
                {zones.map((zone) => (
                  <ZoneCard
                    key={zone.id}
                    zone={zone}
                    onUpdate={handleUpdateZone}
                    onDelete={handleDeleteZone}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'config' && <ConfigManager />}
        {activeTab === 'integrations' && <IntegrationConfig />}
      </main>

      <footer className="app-footer">
        <p>
          <strong>Status:</strong> {status?.redis || 'Unknown'} | 
          <strong> Last Update:</strong> {status?.time ? new Date(status.time).toLocaleString() : 'Never'}
        </p>
      </footer>
    </div>
  );
}

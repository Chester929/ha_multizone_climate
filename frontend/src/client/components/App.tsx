import React, { useState, useEffect, useCallback } from 'react';
import { Zone, SystemStatus } from '../types';
import { useWebSocket } from '../hooks/useWebSocket';
import { ZoneCard } from './ZoneCard';
import { ConfigManager } from './ConfigManager';
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
  const [activeTab, setActiveTab] = useState<'zones' | 'config'>('zones');
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
        }),
      });

      if (response.ok) {
        fetchZones();
      } else {
        alert('Failed to update zone');
      }
    } catch (error) {
      console.error('Error updating zone:', error);
      alert('Failed to update zone');
    }
  };

  const handleDeleteZone = async (id: string) => {
    if (!confirm('Are you sure you want to delete this zone?')) {
      return;
    }

    try {
      const response = await fetch(`/api/zones/${id}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        fetchZones();
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
    
    const newZone = {
      id: formData.get('id') as string,
      name: formData.get('name') as string,
      enabled: 'true',
      target_temperature: formData.get('target_temperature') as string,
      priority: formData.get('priority') as string,
    };

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
        alert('Failed to create zone');
      }
    } catch (error) {
      console.error('Error creating zone:', error);
      alert('Failed to create zone');
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
                  <input type="text" name="id" required />
                </div>
                <div className="form-group">
                  <label>Zone Name</label>
                  <input type="text" name="name" required />
                </div>
                <div className="form-group">
                  <label>Target Temperature (°C)</label>
                  <input type="number" name="target_temperature" step="0.5" required />
                </div>
                <div className="form-group">
                  <label>Priority</label>
                  <input type="number" name="priority" defaultValue="0" />
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

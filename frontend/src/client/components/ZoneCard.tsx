import React, { useState, useEffect } from 'react';
import { Zone } from '../types';
import { TemperatureChart } from './TemperatureChart';

interface ZoneCardProps {
  zone: Zone;
  onUpdate: (zone: Zone) => void;
  onDelete: (id: string) => void;
}

export function ZoneCard({ zone, onUpdate, onDelete }: ZoneCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [showChart, setShowChart] = useState(false);
  const [editedZone, setEditedZone] = useState(zone);
  const [sliderValue, setSliderValue] = useState(zone.target_temperature || '20');

  // Sync editedZone when zone prop changes (e.g., from WebSocket updates)
  useEffect(() => {
    setEditedZone(zone);
    setSliderValue(zone.target_temperature || '20');
  }, [zone]);

  const handleSave = () => {
    // Validate target_temperature before saving
    if (editedZone.target_temperature !== undefined && editedZone.target_temperature !== null) {
      const temp = parseFloat(editedZone.target_temperature as string);
      if (isNaN(temp) || editedZone.target_temperature.toString().trim() === '') {
        alert('Please enter a valid numeric target temperature before saving.');
        return;
      }
    }
    
    onUpdate(editedZone);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditedZone(zone);
    setIsEditing(false);
  };
  
  const handleDelete = () => {
    if (confirm(`Are you sure you want to delete zone "${zone.name || zone.id}"?`)) {
      onDelete(zone.id);
    }
  };

  // Handle slider value changes - only update if value actually changed
  const handleSliderRelease = () => {
    // Ensure string comparison by converting both values
    const currentTemp = String(zone.target_temperature || '20');
    const newTemp = String(sliderValue);
    
    if (newTemp !== currentTemp) {
      const updated = { ...editedZone, target_temperature: sliderValue };
      setEditedZone(updated);
      onUpdate(updated);
    }
  };

  return (
    <div className="zone-card">
      <div className="zone-header">
        <div className="zone-name">
          {isEditing ? (
            <input
              type="text"
              value={editedZone.name}
              onChange={(e) => setEditedZone({ ...editedZone, name: e.target.value })}
              className="zone-name-input"
            />
          ) : (
            zone.name || zone.id
          )}
        </div>
        <div className="zone-actions">
          <label className="zone-toggle">
            <input
              type="checkbox"
              checked={editedZone.enabled}
              onChange={(e) => {
                const updated = { ...editedZone, enabled: e.target.checked };
                setEditedZone(updated);
                if (!isEditing) {
                  onUpdate(updated);
                }
              }}
              disabled={isEditing}
            />
            <span className={`zone-status ${editedZone.enabled ? 'enabled' : 'disabled'}`}>
              {editedZone.enabled ? 'Enabled' : 'Disabled'}
            </span>
          </label>
        </div>
      </div>

      <div className="zone-details">
        <div className="zone-detail">
          <div className="detail-label">Current Temperature</div>
          <div className="detail-value">{zone.current_temperature || 'N/A'}°C</div>
        </div>
        <div className="zone-detail">
          <div className="detail-label">Target Temperature</div>
          {isEditing ? (
            <input
              type="number"
              step="0.5"
              value={editedZone.target_temperature || ''}
              onChange={(e) => setEditedZone({ ...editedZone, target_temperature: e.target.value })}
              className="detail-input"
            />
          ) : (
            <div className="detail-value">{zone.target_temperature || 'N/A'}°C</div>
          )}
        </div>
        {!isEditing && (
          <div className="zone-detail zone-detail-full">
            <div className="detail-label">
              Adjust Temperature: {sliderValue}°C
            </div>
            <div className="temperature-slider-container">
              <span className="slider-label">10°C</span>
              <input
                type="range"
                min="10"
                max="30"
                step="0.5"
                value={sliderValue}
                onChange={(e) => {
                  setSliderValue(e.target.value);
                }}
                onMouseUp={handleSliderRelease}
                onTouchEnd={handleSliderRelease}
                className="temperature-slider"
              />
              <span className="slider-label">30°C</span>
            </div>
          </div>
        )}
        <div className="zone-detail">
          <div className="detail-label">Satisfaction</div>
          <div className="detail-value">{zone.satisfaction || 'Unknown'}</div>
        </div>
        <div className="zone-detail">
          <div className="detail-label">Valve State</div>
          <div className="detail-value">{zone.valve_state || 'Unknown'}</div>
        </div>
        {isEditing && (
          <div className="zone-detail">
            <div className="detail-label">Priority</div>
            <input
              type="number"
              value={editedZone.priority || 0}
              onChange={(e) => setEditedZone({ ...editedZone, priority: parseInt(e.target.value, 10) || 0 })}
              className="detail-input"
            />
          </div>
        )}
      </div>

      <div className="zone-controls">
        {isEditing ? (
          <>
            <button onClick={handleSave} className="btn btn-primary">Save</button>
            <button onClick={handleCancel} className="btn btn-secondary">Cancel</button>
          </>
        ) : (
          <>
            <button onClick={() => setIsEditing(true)} className="btn btn-primary">Edit</button>
            <button onClick={() => setShowChart(!showChart)} className="btn btn-secondary">
              {showChart ? 'Hide Chart' : 'Show Chart'}
            </button>
            <button onClick={handleDelete} className="btn btn-danger">Delete</button>
          </>
        )}
      </div>

      {showChart && !isEditing && (
        <TemperatureChart zoneId={zone.id} zoneName={zone.name || zone.id} />
      )}
    </div>
  );
}

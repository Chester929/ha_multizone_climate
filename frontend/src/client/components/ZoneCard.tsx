import React, { useState, useEffect } from 'react';
import { Zone } from '../types';
import { TemperatureChart } from './TemperatureChart';
import { useDefaults } from '../hooks/useDefaults';
import { EntitySelector, Entity } from './EntitySelector';

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
  const { defaults } = useDefaults();
  const [entityIdErrors, setEntityIdErrors] = useState({
    temperature_sensor: '',
    valve_switch: '',
    climate: ''
  });

  // Entity ID validation pattern
  const entityIDPattern = /^[a-z_]+\.[a-z0-9_]+$/;

  // Sync editedZone when zone prop changes (e.g., from WebSocket updates)
  useEffect(() => {
    setEditedZone(zone);
    setSliderValue(zone.target_temperature || '20');
  }, [zone]);

  const handleSave = () => {
    // Validate entity IDs before saving
    const errors = { temperature_sensor: '', valve_switch: '', climate: '' };
    let hasErrors = false;

    if (editedZone.temperature_sensor_entity_id && !entityIDPattern.test(editedZone.temperature_sensor_entity_id)) {
      errors.temperature_sensor = 'Invalid format. Expected: domain.entity_name (e.g., sensor.temperature)';
      hasErrors = true;
    }

    if (editedZone.valve_switch_entity_id && !entityIDPattern.test(editedZone.valve_switch_entity_id)) {
      errors.valve_switch = 'Invalid format. Expected: domain.entity_name (e.g., switch.valve)';
      hasErrors = true;
    }

    if (editedZone.climate_entity_id && !entityIDPattern.test(editedZone.climate_entity_id)) {
      errors.climate = 'Invalid format. Expected: domain.entity_name (e.g., climate.zone)';
      hasErrors = true;
    }

    if (hasErrors) {
      setEntityIdErrors(errors);
      return;
    }

    // Clear errors if validation passed
    setEntityIdErrors({ temperature_sensor: '', valve_switch: '', climate: '' });

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

  const handleClimateEntityChange = (entityId: string, entity?: Entity) => {
    const newZone = { ...editedZone, climate_entity_id: entityId };
    
    if (entity) {
      // Auto-load target temperature from climate entity if not already set
      if (entity.temperature !== undefined && !editedZone.target_temperature) {
        newZone.target_temperature = entity.temperature.toString();
        setSliderValue(entity.temperature.toString());
      }
    }
    
    setEditedZone(newZone);
  };

  const handleTempSensorChange = (entityId: string) => {
    setEditedZone({ ...editedZone, temperature_sensor_entity_id: entityId });
  };

  const handleValveSwitchChange = (entityId: string) => {
    setEditedZone({ ...editedZone, valve_switch_entity_id: entityId });
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
                onKeyUp={handleSliderRelease}
                className="temperature-slider"
                aria-label="Adjust target temperature"
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
          <>
            <div className="zone-detail zone-detail-full">
              <div className="detail-label">Climate Entity (Optional)</div>
              <EntitySelector
                value={editedZone.climate_entity_id || ''}
                onChange={handleClimateEntityChange}
                domains="climate"
                placeholder="climate.bedroom_thermostat"
              />
              <small style={{ fontSize: '0.85em', color: '#666', marginTop: '0.25rem', display: 'block' }}>
                Link to existing HA climate entity for synchronized control
              </small>
            </div>
            <div className="zone-detail zone-detail-full">
              <div className="detail-label">Temperature Sensor Entity</div>
              <EntitySelector
                value={editedZone.temperature_sensor_entity_id || ''}
                onChange={handleTempSensorChange}
                domains="sensor"
                placeholder="sensor.bedroom_temperature"
              />
              {entityIdErrors.temperature_sensor && (
                <span className="error-message">{entityIdErrors.temperature_sensor}</span>
              )}
            </div>
            <div className="zone-detail zone-detail-full">
              <div className="detail-label">Valve Switch Entity</div>
              <EntitySelector
                value={editedZone.valve_switch_entity_id || ''}
                onChange={handleValveSwitchChange}
                domains={['switch', 'valve']}
                placeholder="switch.bedroom_valve"
              />
              {entityIdErrors.valve_switch && (
                <span className="error-message">{entityIdErrors.valve_switch}</span>
              )}
            </div>
            <div className="zone-detail">
              <div className="detail-label">Priority</div>
              <input
                type="number"
                min="0"
                max="100"
                value={editedZone.priority || 0}
                onChange={(e) => setEditedZone({ ...editedZone, priority: parseInt(e.target.value, 10) || 0 })}
                className="detail-input"
              />
            </div>
            <div className="zone-detail">
              <div className="detail-label">Opening Offset (°C)</div>
              <input
                type="number"
                step="0.1"
                min="0"
                max="5"
                value={editedZone.opening_offset ?? defaults?.zone.opening_offset ?? 0.3}
                onChange={(e) => setEditedZone({ ...editedZone, opening_offset: parseFloat(e.target.value) || 0.3 })}
                className="detail-input"
              />
            </div>
            <div className="zone-detail">
              <div className="detail-label">Closing Offset (°C)</div>
              <input
                type="number"
                step="0.1"
                min="0"
                max="5"
                value={editedZone.closing_offset ?? defaults?.zone.closing_offset ?? 0.3}
                onChange={(e) => setEditedZone({ ...editedZone, closing_offset: parseFloat(e.target.value) || 0.3 })}
                className="detail-input"
              />
            </div>
            <div className="zone-detail">
              <div className="detail-label">Fallback Valve</div>
              <label className="zone-toggle">
                <input
                  type="checkbox"
                  checked={editedZone.is_fallback_valve || false}
                  onChange={(e) => setEditedZone({ ...editedZone, is_fallback_valve: e.target.checked })}
                />
                <span>Enable as fallback valve</span>
              </label>
            </div>
          </>
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

import React, { useState, useEffect, useMemo } from 'react';

export interface Entity {
  entity_id: string;
  friendly_name?: string;
  state?: string;
  current_temperature?: number;
  temperature?: number;
}

interface EntitySelectorProps {
  value: string;
  onChange: (entityId: string, entity?: Entity) => void;
  domain?: string;
  placeholder?: string;
  disabled?: boolean;
  name?: string;
  required?: boolean;
}

export function EntitySelector({
  value,
  onChange,
  domain,
  placeholder = 'Select an entity...',
  disabled = false,
  name,
  required = false,
}: EntitySelectorProps) {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);

  // Fetch entities from the backend
  useEffect(() => {
    const fetchEntities = async () => {
      setLoading(true);
      setError(null);
      try {
        const url = domain 
          ? `/api/ha/entities?domain=${domain}` 
          : '/api/ha/entities';
        
        const response = await fetch(url);
        
        if (!response.ok) {
          if (response.status === 503) {
            setError('Home Assistant integration is not enabled');
            setEntities([]);
            return;
          }
          throw new Error(`Failed to fetch entities: ${response.status}`);
        }
        
        const data = await response.json();
        setEntities(data.entities || []);
      } catch (err) {
        console.error('Error fetching entities:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch entities');
        setEntities([]);
      } finally {
        setLoading(false);
      }
    };

    fetchEntities();
  }, [domain]);

  // Filter entities based on search term
  const filteredEntities = useMemo(() => {
    if (!searchTerm) return entities;
    
    const lowerSearch = searchTerm.toLowerCase();
    return entities.filter((entity) => {
      const entityIdMatch = entity.entity_id.toLowerCase().includes(lowerSearch);
      const friendlyNameMatch = entity.friendly_name?.toLowerCase().includes(lowerSearch);
      return entityIdMatch || friendlyNameMatch;
    });
  }, [entities, searchTerm]);

  // Get the display text for the selected value
  const selectedEntity = entities.find((e) => e.entity_id === value);
  const displayText = selectedEntity?.friendly_name || value || '';

  const handleSelect = (entity: Entity) => {
    onChange(entity.entity_id, entity);
    setShowDropdown(false);
    setSearchTerm('');
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(e.target.value);
    setShowDropdown(true);
  };

  const handleFocus = () => {
    setShowDropdown(true);
  };

  const handleBlur = () => {
    // Delay hiding dropdown to allow click events to fire
    setTimeout(() => setShowDropdown(false), 200);
  };

  const handleClear = () => {
    onChange('');
    setSearchTerm('');
  };

  if (loading) {
    return (
      <div className="entity-selector">
        <input
          type="text"
          value="Loading entities..."
          disabled
          className="entity-selector-input"
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="entity-selector">
        <input
          type="text"
          name={name}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          pattern="^[a-z_]+\.[a-z0-9_]+$"
          title="Format: domain.entity_name (e.g., climate.zone)"
        />
        <small style={{ color: '#888', display: 'block', marginTop: '0.25rem' }}>
          {error} - Enter manually
        </small>
      </div>
    );
  }

  return (
    <div className="entity-selector">
      <div className="entity-selector-container">
        <input
          type="text"
          name={name}
          value={showDropdown ? searchTerm : displayText}
          onChange={handleInputChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          className="entity-selector-input"
          autoComplete="off"
        />
        {value && !disabled && (
          <button
            type="button"
            className="entity-selector-clear"
            onClick={handleClear}
            aria-label="Clear selection"
          >
            ✕
          </button>
        )}
      </div>

      {showDropdown && filteredEntities.length > 0 && (
        <div className="entity-selector-dropdown">
          {filteredEntities.map((entity) => (
            <div
              key={entity.entity_id}
              className={`entity-selector-option ${entity.entity_id === value ? 'selected' : ''}`}
              onClick={() => handleSelect(entity)}
            >
              <div className="entity-option-name">
                {entity.friendly_name || entity.entity_id}
              </div>
              <div className="entity-option-id">{entity.entity_id}</div>
            </div>
          ))}
        </div>
      )}

      {showDropdown && filteredEntities.length === 0 && searchTerm && (
        <div className="entity-selector-dropdown">
          <div className="entity-selector-option disabled">
            No entities found
          </div>
        </div>
      )}

      {/* Hidden input to store the actual entity_id value for form submission */}
      <input
        type="hidden"
        name={name}
        value={value}
      />
    </div>
  );
}

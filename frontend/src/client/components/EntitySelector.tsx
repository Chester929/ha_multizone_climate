import React, { useState, useEffect } from 'react';

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
  domains?: string | string[]; // Single domain or array of domains
  placeholder?: string;
  disabled?: boolean;
  name?: string;
  required?: boolean;
}

export function EntitySelector({
  value,
  onChange,
  domains,
  placeholder = 'Enter entity ID (e.g., sensor.temperature)',
  disabled = false,
  name,
  required = false,
}: EntitySelectorProps) {
  const [entities, setEntities] = useState<Array<{ entity_id: string; friendly_name: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);

  // Fetch entities from API when component mounts or domains change
  useEffect(() => {
    const fetchEntities = async () => {
      if (!domains) {
        // If no domains specified, don't fetch entities (use manual entry)
        setEntities([]);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        // Convert domains to comma-separated string
        const domainsParam = Array.isArray(domains) ? domains.join(',') : domains;
        const response = await fetch(`/api/entities?domains=${encodeURIComponent(domainsParam)}`);
        
        if (!response.ok) {
          throw new Error('Failed to fetch entities');
        }

        const data = await response.json();
        setEntities(data || []);
      } catch (err) {
        console.error('Error fetching entities:', err);
        setError('Failed to load entities. You can still enter manually.');
        setEntities([]);
      } finally {
        setLoading(false);
      }
    };

    fetchEntities();
  }, [domains]);

  // Filter entities based on search term
  const filteredEntities = entities.filter((entity) => {
    const searchLower = searchTerm.toLowerCase();
    return (
      entity.entity_id.toLowerCase().includes(searchLower) ||
      entity.friendly_name.toLowerCase().includes(searchLower)
    );
  });

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setSearchTerm(newValue);
    onChange(newValue);
    setShowDropdown(true);
  };

  const handleSelectEntity = (entityId: string) => {
    setSearchTerm(entityId);
    onChange(entityId);
    setShowDropdown(false);
  };

  const handleInputFocus = () => {
    if (entities.length > 0) {
      setShowDropdown(true);
    }
  };

  const handleInputBlur = () => {
    // Delay hiding dropdown to allow clicking on items
    setTimeout(() => setShowDropdown(false), 200);
  };

  // Use the value prop if it's set (controlled component)
  const inputValue = value || searchTerm;

  return (
    <div className="entity-selector">
      <div className="entity-input-wrapper">
        <input
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          onBlur={handleInputBlur}
          placeholder={placeholder}
          disabled={disabled || loading}
          name={name}
          required={required}
          className="entity-input"
          autoComplete="off"
        />
        {loading && <span className="entity-loading">Loading...</span>}
      </div>
      
      {error && <small className="entity-error" style={{ color: '#f44336' }}>{error}</small>}
      
      {domains && (
        <small className="entity-hint">
          Expected format: {Array.isArray(domains) ? domains.join(' or ') : domains}.entity_name
        </small>
      )}

      {showDropdown && filteredEntities.length > 0 && (
        <div className="entity-dropdown">
          {filteredEntities.slice(0, 50).map((entity) => (
            <div
              key={entity.entity_id}
              className="entity-dropdown-item"
              onMouseDown={() => handleSelectEntity(entity.entity_id)}
            >
              <div className="entity-dropdown-name">{entity.friendly_name}</div>
              <div className="entity-dropdown-id">{entity.entity_id}</div>
            </div>
          ))}
          {filteredEntities.length > 50 && (
            <div className="entity-dropdown-footer">
              Showing 50 of {filteredEntities.length} entities. Refine your search for more.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

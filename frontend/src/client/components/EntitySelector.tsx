import React from 'react';

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
  placeholder = 'Enter entity ID (e.g., sensor.temperature)',
  disabled = false,
  name,
  required = false,
}: EntitySelectorProps) {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const entityId = e.target.value;
    onChange(entityId);
  };

  return (
    <div className="entity-selector">
      <input
        type="text"
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        disabled={disabled}
        name={name}
        required={required}
        className="entity-input"
      />
      {domain && (
        <small className="entity-hint">
          Expected format: {domain}.entity_name
        </small>
      )}
    </div>
  );
}

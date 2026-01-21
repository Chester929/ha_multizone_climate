import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EntitySelector } from '../EntitySelector';

describe('EntitySelector Component', () => {
  const mockOnChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders with placeholder text', () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ entities: [], count: 0 }),
    });

    render(
      <EntitySelector
        value=""
        onChange={mockOnChange}
        placeholder="Select entity"
      />
    );

    expect(screen.getByPlaceholderText('Select entity')).toBeInTheDocument();
  });

  it('fetches entities on mount', async () => {
    const mockEntities = [
      { entity_id: 'climate.living_room', friendly_name: 'Living Room Climate', state: 'heat' },
      { entity_id: 'climate.bedroom', friendly_name: 'Bedroom Climate', state: 'off' },
    ];

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ entities: mockEntities, count: 2 }),
    });

    render(
      <EntitySelector
        value=""
        onChange={mockOnChange}
        domain="climate"
      />
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/ha/entities?domain=climate');
    });
  });

  it('displays entities in dropdown when input is focused', async () => {
    const mockEntities = [
      { entity_id: 'climate.living_room', friendly_name: 'Living Room Climate', state: 'heat' },
      { entity_id: 'climate.bedroom', friendly_name: 'Bedroom Climate', state: 'off' },
    ];

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ entities: mockEntities, count: 2 }),
    });

    render(
      <EntitySelector
        value=""
        onChange={mockOnChange}
        domain="climate"
      />
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });

    const input = screen.getByRole('textbox');
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByText('Living Room Climate')).toBeInTheDocument();
      expect(screen.getByText('Bedroom Climate')).toBeInTheDocument();
    });
  });

  it('filters entities based on search term', async () => {
    const mockEntities = [
      { entity_id: 'climate.living_room', friendly_name: 'Living Room Climate', state: 'heat' },
      { entity_id: 'climate.bedroom', friendly_name: 'Bedroom Climate', state: 'off' },
    ];

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ entities: mockEntities, count: 2 }),
    });

    render(
      <EntitySelector
        value=""
        onChange={mockOnChange}
        domain="climate"
      />
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'living' } });

    await waitFor(() => {
      expect(screen.getByText('Living Room Climate')).toBeInTheDocument();
      expect(screen.queryByText('Bedroom Climate')).not.toBeInTheDocument();
    });
  });

  it('calls onChange when entity is selected', async () => {
    const mockEntities = [
      { entity_id: 'climate.living_room', friendly_name: 'Living Room Climate', state: 'heat' },
    ];

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ entities: mockEntities, count: 1 }),
    });

    render(
      <EntitySelector
        value=""
        onChange={mockOnChange}
        domain="climate"
      />
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });

    const input = screen.getByRole('textbox');
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByText('Living Room Climate')).toBeInTheDocument();
    });

    const option = screen.getByText('Living Room Climate');
    fireEvent.click(option);

    expect(mockOnChange).toHaveBeenCalledWith('climate.living_room', mockEntities[0]);
  });

  it('displays selected entity friendly name', async () => {
    const mockEntities = [
      { entity_id: 'climate.living_room', friendly_name: 'Living Room Climate', state: 'heat' },
    ];

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ entities: mockEntities, count: 1 }),
    });

    render(
      <EntitySelector
        value="climate.living_room"
        onChange={mockOnChange}
        domain="climate"
      />
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });

    await waitFor(() => {
      const input = screen.getByRole('textbox');
      expect(input).toHaveValue('Living Room Climate');
    });
  });

  it('shows error message when HA integration is not enabled', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ error: 'Home Assistant integration is not enabled' }),
    });

    render(
      <EntitySelector
        value=""
        onChange={mockOnChange}
        domain="climate"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Home Assistant integration is not enabled/)).toBeInTheDocument();
    });
  });

  it('allows manual entry when HA integration is not available', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 503,
    });

    render(
      <EntitySelector
        value=""
        onChange={mockOnChange}
        placeholder="climate.living_room"
      />
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });

    const input = screen.getByPlaceholderText('climate.living_room');
    fireEvent.change(input, { target: { value: 'climate.manual_entry' } });

    expect(mockOnChange).toHaveBeenCalledWith('climate.manual_entry');
  });

  it('clears selection when clear button is clicked', async () => {
    const mockEntities = [
      { entity_id: 'climate.living_room', friendly_name: 'Living Room Climate', state: 'heat' },
    ];

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ entities: mockEntities, count: 1 }),
    });

    render(
      <EntitySelector
        value="climate.living_room"
        onChange={mockOnChange}
        domain="climate"
      />
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });

    const clearButton = screen.getByLabelText('Clear selection');
    fireEvent.click(clearButton);

    expect(mockOnChange).toHaveBeenCalledWith('');
  });

  it('shows "No entities found" when search has no results', async () => {
    const mockEntities = [
      { entity_id: 'climate.living_room', friendly_name: 'Living Room Climate', state: 'heat' },
    ];

    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ entities: mockEntities, count: 1 }),
    });

    render(
      <EntitySelector
        value=""
        onChange={mockOnChange}
        domain="climate"
      />
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'nonexistent' } });

    await waitFor(() => {
      expect(screen.getByText('No entities found')).toBeInTheDocument();
    });
  });

  it('respects disabled prop', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ entities: [], count: 0 }),
    });

    render(
      <EntitySelector
        value=""
        onChange={mockOnChange}
        disabled={true}
      />
    );

    const input = screen.getByRole('textbox');
    expect(input).toBeDisabled();
  });
});

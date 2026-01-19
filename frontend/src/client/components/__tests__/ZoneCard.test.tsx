import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ZoneCard } from '../ZoneCard';
import { Zone } from '../../types';

// Mock TemperatureChart component
jest.mock('../TemperatureChart', () => ({
  TemperatureChart: () => <div>Temperature Chart Mock</div>,
}));

describe('ZoneCard Component', () => {
  const mockZone: Zone = {
    id: 'zone-1',
    name: 'Living Room',
    enabled: true,
    current_temperature: '22.5',
    target_temperature: '23.0',
    satisfaction: 'satisfied',
    valve_state: 'open',
    priority: 1,
  };

  const mockOnUpdate = jest.fn();
  const mockOnDelete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders zone information correctly', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    expect(screen.getByText('Living Room')).toBeInTheDocument();
    expect(screen.getByText('22.5°C')).toBeInTheDocument();
    expect(screen.getByText('23.0°C')).toBeInTheDocument();
    expect(screen.getByText('satisfied')).toBeInTheDocument();
    expect(screen.getByText('open')).toBeInTheDocument();
  });

  it('enables edit mode when edit button is clicked', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const editButton = screen.getByText('Edit');
    fireEvent.click(editButton);

    expect(screen.getByText('Save')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();
  });

  it('calls onUpdate when toggling enabled state', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);

    expect(mockOnUpdate).toHaveBeenCalledWith({
      ...mockZone,
      enabled: false,
    });
  });

  it('calls onDelete when delete button is clicked', () => {
    window.confirm = jest.fn(() => true);
    
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const deleteButton = screen.getByText('Delete');
    fireEvent.click(deleteButton);

    expect(mockOnDelete).toHaveBeenCalledWith('zone-1');
  });

  it('shows chart when show chart button is clicked', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const chartButton = screen.getByText('Show Chart');
    fireEvent.click(chartButton);

    expect(screen.getByText('Temperature Chart Mock')).toBeInTheDocument();
    expect(screen.getByText('Hide Chart')).toBeInTheDocument();
  });

  it('saves changes when save button is clicked in edit mode', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const editButton = screen.getByText('Edit');
    fireEvent.click(editButton);

    const saveButton = screen.getByText('Save');
    fireEvent.click(saveButton);

    expect(mockOnUpdate).toHaveBeenCalled();
  });

  it('cancels edit mode when cancel button is clicked', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const editButton = screen.getByText('Edit');
    fireEvent.click(editButton);

    expect(screen.getByText('Save')).toBeInTheDocument();

    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);

    expect(screen.getByText('Edit')).toBeInTheDocument();
  });

  it('displays temperature slider with correct range', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const slider = screen.getByRole('slider');
    expect(slider).toBeInTheDocument();
    expect(slider).toHaveAttribute('min', '10');
    expect(slider).toHaveAttribute('max', '30');
    expect(slider).toHaveAttribute('step', '0.5');
  });

  it('updates slider value when changed', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const slider = screen.getByRole('slider') as HTMLInputElement;
    expect(slider.value).toBe('23.0');

    fireEvent.change(slider, { target: { value: '25.0' } });
    expect(slider.value).toBe('25.0');
  });

  it('calls onUpdate when slider is released with mouse', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '25.0' } });
    fireEvent.mouseUp(slider);

    expect(mockOnUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        target_temperature: '25.0',
      })
    );
  });

  it('calls onUpdate when slider is released with touch', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '24.5' } });
    fireEvent.touchEnd(slider);

    expect(mockOnUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        target_temperature: '24.5',
      })
    );
  });

  it('calls onUpdate when slider is released with keyboard', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '21.0' } });
    fireEvent.keyUp(slider);

    expect(mockOnUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        target_temperature: '21.0',
      })
    );
  });

  it('does not call onUpdate if slider value unchanged', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const slider = screen.getByRole('slider');
    // Don't change the value, just release
    fireEvent.mouseUp(slider);

    expect(mockOnUpdate).not.toHaveBeenCalled();
  });

  it('displays slider label with current temperature value', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    expect(screen.getByText(/Adjust Temperature: 23.0°C/i)).toBeInTheDocument();
  });

  it('hides slider when in edit mode', () => {
    render(<ZoneCard zone={mockZone} onUpdate={mockOnUpdate} onDelete={mockOnDelete} />);

    const editButton = screen.getByText('Edit');
    fireEvent.click(editButton);

    const slider = screen.queryByRole('slider');
    expect(slider).not.toBeInTheDocument();
  });
});

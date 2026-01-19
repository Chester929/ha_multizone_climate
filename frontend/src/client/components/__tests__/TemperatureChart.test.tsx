import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { TemperatureChart } from '../TemperatureChart';

// Mock fetch
global.fetch = jest.fn();

// Mock Chart.js
jest.mock('react-chartjs-2', () => ({
  Line: () => <div>Mocked Line Chart</div>,
}));

jest.mock('chart.js', () => ({
  Chart: {
    register: jest.fn(),
  },
  CategoryScale: jest.fn(),
  LinearScale: jest.fn(),
  PointElement: jest.fn(),
  LineElement: jest.fn(),
  Title: jest.fn(),
  Tooltip: jest.fn(),
  Legend: jest.fn(),
  TimeScale: jest.fn(),
}));

describe('TemperatureChart Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('displays loading state initially', () => {
    (global.fetch as jest.Mock).mockImplementation(() => 
      new Promise(() => {}) // Never resolves
    );

    render(<TemperatureChart zoneId="zone-1" zoneName="Living Room" />);
    expect(screen.getByText(/Loading chart data/i)).toBeInTheDocument();
  });

  it('fetches and displays historical data', async () => {
    const mockData = [
      {
        timestamp: '2026-01-19T10:00:00Z',
        current_temperature: '22.5',
        target_temperature: '23.0',
      },
      {
        timestamp: '2026-01-19T11:00:00Z',
        current_temperature: '23.0',
        target_temperature: '23.0',
      },
    ];

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    });

    render(<TemperatureChart zoneId="zone-1" zoneName="Living Room" />);

    await waitFor(() => {
      expect(screen.getByText('Mocked Line Chart')).toBeInTheDocument();
    });
  });

  it('displays no data message when history is empty', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    render(<TemperatureChart zoneId="zone-1" zoneName="Living Room" />);

    await waitFor(() => {
      expect(screen.getByText(/No historical data available/i)).toBeInTheDocument();
    });
  });

  it('uses custom hours parameter when provided', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    render(<TemperatureChart zoneId="zone-1" zoneName="Living Room" hours={12} />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/history/zones/zone-1?hours=12');
    });
  });

  it('handles fetch errors gracefully', async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

    render(<TemperatureChart zoneId="zone-1" zoneName="Living Room" />);

    await waitFor(() => {
      expect(screen.getByText(/No historical data available/i)).toBeInTheDocument();
    });
  });
});

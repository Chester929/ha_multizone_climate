import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { App } from '../App';

// Mock fetch
global.fetch = jest.fn();

// Mock WebSocket
class MockWebSocket {
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: ((error: any) => void) | null = null;
  onmessage: ((event: any) => void) | null = null;
  readyState = 1;
  
  constructor(public url: string) {
    setTimeout(() => {
      if (this.onopen) this.onopen();
    }, 0);
  }
  
  send(data: string) {}
  close() {}
}

(global as any).WebSocket = MockWebSocket;

describe('App Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders without crashing', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ([]),
    }).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', redis: 'connected' }),
    });

    render(<App />);
    
    await waitFor(() => {
      expect(screen.getByText(/Multizone Climate Control/i)).toBeInTheDocument();
    });
  });

  it('displays loading state initially', () => {
    (global.fetch as jest.Mock).mockImplementation(() => 
      new Promise(() => {}) // Never resolves
    );

    render(<App />);
    expect(screen.getByText(/Loading zones/i)).toBeInTheDocument();
  });

  it('fetches and displays zones', async () => {
    const mockZones = [
      {
        id: 'zone-1',
        name: 'Living Room',
        enabled: 'true',
        current_temperature: '22.5',
        target_temperature: '23.0',
        satisfaction: 'satisfied',
        valve_state: 'open',
      },
    ];

    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockZones,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'healthy', redis: 'connected' }),
      });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Living Room')).toBeInTheDocument();
    });
  });

  it('shows no zones message when zones array is empty', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'healthy', redis: 'connected' }),
      });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/No zones configured yet/i)).toBeInTheDocument();
    });
  });

  it('switches between zones and config tabs', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'healthy', redis: 'connected' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/No zones configured yet/i)).toBeInTheDocument();
    });

    const configTab = screen.getByText(/Configuration/i);
    configTab.click();

    await waitFor(() => {
      expect(screen.getByText(/System Configuration/i)).toBeInTheDocument();
    });
  });

  it('switches to integrations tab and renders IntegrationConfig', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'healthy', redis: 'connected' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/No zones configured yet/i)).toBeInTheDocument();
    });

    const integrationsTab = screen.getByText(/Integrations/i);
    integrationsTab.click();

    await waitFor(() => {
      expect(screen.getByText(/Home Assistant Integration/i)).toBeInTheDocument();
      expect(screen.getByText(/MQTT Integration/i)).toBeInTheDocument();
    });
  });
});

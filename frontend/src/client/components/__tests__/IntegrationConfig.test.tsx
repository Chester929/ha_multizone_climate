import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { IntegrationConfig } from '../IntegrationConfig';

// Mock fetch
global.fetch = jest.fn();

describe('IntegrationConfig Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('displays loading state initially', () => {
    (global.fetch as jest.Mock).mockImplementation(() => 
      new Promise(() => {}) // Never resolves
    );

    render(<IntegrationConfig />);
    expect(screen.getByText(/Loading integration settings/i)).toBeInTheDocument();
  });

  it('fetches and displays integration settings', async () => {
    const mockSettings = {
      ha_enabled: 'false',
      mqtt_enabled: 'false',
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockSettings,
    });

    render(<IntegrationConfig />);

    await waitFor(() => {
      expect(screen.getByText(/Home Assistant Integration/i)).toBeInTheDocument();
      expect(screen.getByText(/MQTT Integration/i)).toBeInTheDocument();
    });
  });

  it('enables edit mode when edit button is clicked', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    render(<IntegrationConfig />);

    await waitFor(() => {
      expect(screen.getByText(/Edit Integration Settings/i)).toBeInTheDocument();
    });

    const editButton = screen.getByText(/Edit Integration Settings/i);
    fireEvent.click(editButton);

    await waitFor(() => {
      expect(screen.getByText(/Save Integration Settings/i)).toBeInTheDocument();
      expect(screen.getByText(/Cancel/i)).toBeInTheDocument();
    });
  });

  it('toggles Home Assistant integration when toggle is clicked', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ha_enabled: 'false' }),
    });

    render(<IntegrationConfig />);

    await waitFor(() => {
      expect(screen.getByText(/Edit Integration Settings/i)).toBeInTheDocument();
    });

    const editButton = screen.getByText(/Edit Integration Settings/i);
    fireEvent.click(editButton);

    const haToggle = screen.getByLabelText(/Enable Home Assistant integration/i);
    expect(haToggle).not.toBeChecked();

    fireEvent.click(haToggle);
    expect(haToggle).toBeChecked();
  });

  it('toggles MQTT integration when toggle is clicked', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ mqtt_enabled: 'false' }),
    });

    render(<IntegrationConfig />);

    await waitFor(() => {
      expect(screen.getByText(/Edit Integration Settings/i)).toBeInTheDocument();
    });

    const editButton = screen.getByText(/Edit Integration Settings/i);
    fireEvent.click(editButton);

    const mqttToggle = screen.getByLabelText(/Enable MQTT integration/i);
    expect(mqttToggle).not.toBeChecked();

    fireEvent.click(mqttToggle);
    expect(mqttToggle).toBeChecked();
  });

  it('saves settings successfully', async () => {
    const mockSettings = {
      ha_enabled: 'false',
      mqtt_enabled: 'false',
    };

    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSettings,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'updated' }),
      });

    render(<IntegrationConfig />);

    await waitFor(() => {
      expect(screen.getByText(/Edit Integration Settings/i)).toBeInTheDocument();
    });

    const editButton = screen.getByText(/Edit Integration Settings/i);
    fireEvent.click(editButton);

    const saveButton = await screen.findByText(/Save Integration Settings/i);
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText(/Integration settings saved successfully!/i)).toBeInTheDocument();
    });
  });

  it('displays error message from backend when save fails', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: 'MQTT port must be between 1 and 65535' }),
      });

    render(<IntegrationConfig />);

    await waitFor(() => {
      expect(screen.getByText(/Edit Integration Settings/i)).toBeInTheDocument();
    });

    const editButton = screen.getByText(/Edit Integration Settings/i);
    fireEvent.click(editButton);

    const saveButton = await screen.findByText(/Save Integration Settings/i);
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText(/MQTT port must be between 1 and 65535/i)).toBeInTheDocument();
    });
  });

  it('displays HA settings fields when HA is enabled', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ha_enabled: 'true' }),
    });

    render(<IntegrationConfig />);

    await waitFor(() => {
      expect(screen.getByText(/Base URL/i)).toBeInTheDocument();
      expect(screen.getByText(/Access Token/i)).toBeInTheDocument();
      expect(screen.getByText(/WebSocket Enabled/i)).toBeInTheDocument();
    });
  });

  it('displays MQTT settings fields when MQTT is enabled', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ mqtt_enabled: 'true' }),
    });

    render(<IntegrationConfig />);

    await waitFor(() => {
      expect(screen.getByText(/Broker/i)).toBeInTheDocument();
      expect(screen.getByText(/Port/i)).toBeInTheDocument();
      expect(screen.getByText(/Username/i)).toBeInTheDocument();
      expect(screen.getByText(/Password/i)).toBeInTheDocument();
    });
  });

  it('test connection button is disabled when editing', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ha_enabled: 'true', ha_base_url: 'http://test', ha_token: 'test-token' }),
    });

    render(<IntegrationConfig />);

    await waitFor(() => {
      expect(screen.getByText(/Test Connection/i)).toBeInTheDocument();
    });

    const editButton = screen.getByText(/Edit Integration Settings/i);
    fireEvent.click(editButton);

    // Test Connection button should not be visible in edit mode
    await waitFor(() => {
      expect(screen.queryByText(/Test Connection/i)).not.toBeInTheDocument();
    });
  });
});

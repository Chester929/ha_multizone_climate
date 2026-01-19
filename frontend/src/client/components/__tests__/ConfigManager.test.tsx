import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ConfigManager } from '../ConfigManager';

// Mock fetch
global.fetch = jest.fn();

describe('ConfigManager Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('displays loading state initially', () => {
    (global.fetch as jest.Mock).mockImplementation(() => 
      new Promise(() => {}) // Never resolves
    );

    render(<ConfigManager />);
    expect(screen.getByText(/Loading configuration/i)).toBeInTheDocument();
  });

  it('fetches and displays configuration', async () => {
    const mockConfig = {
      main_target_temperature: '22.0',
      mode: 'heating',
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfig,
    });

    render(<ConfigManager />);

    await waitFor(() => {
      expect(screen.getByText(/System Configuration/i)).toBeInTheDocument();
    });
  });

  it('enables edit mode when edit button is clicked', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    render(<ConfigManager />);

    await waitFor(() => {
      expect(screen.getByText(/Edit Configuration/i)).toBeInTheDocument();
    });

    const editButton = screen.getByText(/Edit Configuration/i);
    fireEvent.click(editButton);

    expect(screen.getByText(/Save Configuration/i)).toBeInTheDocument();
    expect(screen.getByText(/Cancel/i)).toBeInTheDocument();
  });

  it('saves configuration when save button is clicked', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'updated' }),
      });

    render(<ConfigManager />);

    await waitFor(() => {
      expect(screen.getByText(/Edit Configuration/i)).toBeInTheDocument();
    });

    const editButton = screen.getByText(/Edit Configuration/i);
    fireEvent.click(editButton);

    const saveButton = screen.getByText(/Save Configuration/i);
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/config',
        expect.objectContaining({
          method: 'PUT',
        })
      );
    });
  });

  it('exports configuration as JSON', async () => {
    const mockConfig = {
      main_target_temperature: '22.0',
      mode: 'heating',
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfig,
    });

    // Mock createElement and click
    const mockClick = jest.fn();
    const mockSetAttribute = jest.fn();
    
    const originalCreateElement = document.createElement.bind(document);
    jest.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
      if (tagName === 'a') {
        const mockElement = {
          setAttribute: mockSetAttribute,
          click: mockClick,
        };
        return mockElement as any;
      }
      return originalCreateElement(tagName);
    });

    render(<ConfigManager />);

    await waitFor(() => {
      expect(screen.getByText(/Export Config/i)).toBeInTheDocument();
    });

    const exportButton = screen.getByText(/Export Config/i);
    fireEvent.click(exportButton);

    expect(mockClick).toHaveBeenCalled();
    
    jest.restoreAllMocks();
  });

  it('validates imported configuration', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    window.alert = jest.fn();

    render(<ConfigManager />);

    await waitFor(() => {
      expect(screen.getByText(/Import Config/i)).toBeInTheDocument();
    });

    // Simulate file import with invalid data
    const fileInput = screen.getByText(/Import Config/i).querySelector('input') as HTMLInputElement;
    
    const invalidFile = new File(['{"key": 123}'], 'config.json', { type: 'application/json' });
    Object.defineProperty(fileInput, 'files', {
      value: [invalidFile],
    });

    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Invalid configuration file'));
    });
  });

  it('accepts valid imported configuration', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    render(<ConfigManager />);

    await waitFor(() => {
      expect(screen.getByText(/Import Config/i)).toBeInTheDocument();
    });

    // Simulate file import with valid data
    const fileInput = screen.getByText(/Import Config/i).querySelector('input') as HTMLInputElement;
    
    const validFile = new File(['{"main_target_temperature": "23.0"}'], 'config.json', { type: 'application/json' });
    Object.defineProperty(fileInput, 'files', {
      value: [validFile],
    });

    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(screen.getByText(/Save Configuration/i)).toBeInTheDocument();
    });
  });
});

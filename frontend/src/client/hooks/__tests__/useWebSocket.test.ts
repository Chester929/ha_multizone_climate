import { renderHook, waitFor } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';

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
  close() {
    if (this.onclose) this.onclose();
  }
}

describe('useWebSocket Hook', () => {
  let originalWebSocket: any;

  beforeAll(() => {
    originalWebSocket = global.WebSocket;
    (global as any).WebSocket = MockWebSocket;
  });

  afterAll(() => {
    global.WebSocket = originalWebSocket;
  });

  it('connects to WebSocket on mount', async () => {
    const { result } = renderHook(() => useWebSocket('/ws'));

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    });
  });

  it('receives and parses messages', async () => {
    const { result } = renderHook(() => useWebSocket('/ws'));

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    });

    // Simulate receiving a message
    const mockMessage = {
      type: 'zone-update',
      data: { id: 'zone-1', temperature: 22.5 },
      timestamp: new Date().toISOString(),
    };

    const ws = (global.WebSocket as any).prototype;
    if (ws.onmessage) {
      ws.onmessage({ data: JSON.stringify(mockMessage) });
    }

    await waitFor(() => {
      expect(result.current.lastMessage).toEqual(mockMessage);
    });
  });

  it('handles disconnection', async () => {
    const { result } = renderHook(() => useWebSocket('/ws'));

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    });

    // Simulate disconnection
    const ws = (global.WebSocket as any).prototype;
    if (ws.onclose) {
      ws.onclose();
    }

    await waitFor(() => {
      expect(result.current.connected).toBe(false);
    });
  });
});

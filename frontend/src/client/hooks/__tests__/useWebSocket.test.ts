import { renderHook, waitFor } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: ((error: any) => void) | null = null;
  onmessage: ((event: any) => void) | null = null;
  readyState = 1;
  
  constructor(public url: string) {
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      if (this.onopen) {
        this.onopen();
      }
    }, 10);
  }
  
  send(data: string) {}
  close() {
    this.readyState = 3;
    if (this.onclose) {
      this.onclose();
    }
  }
  
  static resetInstances() {
    MockWebSocket.instances = [];
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

  beforeEach(() => {
    MockWebSocket.resetInstances();
  });

  it('connects to WebSocket on mount', async () => {
    const { result } = renderHook(() => useWebSocket('/ws'));

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    }, { timeout: 3000 });
  });

  it('starts with not connected state', () => {
    const { result } = renderHook(() => useWebSocket('/ws'));
    
    // Initially not connected
    expect(result.current.lastMessage).toBe(null);
  });

  it('receives and parses WebSocket messages', async () => {
    const { result } = renderHook(() => useWebSocket('/ws'));

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    });

    // Get the WebSocket instance and trigger a message
    const ws = MockWebSocket.instances[0];
    const mockMessage = {
      type: 'zone-update',
      data: { id: 'zone-1', temperature: 22.5 },
      timestamp: new Date().toISOString(),
    };

    if (ws.onmessage) {
      ws.onmessage({ data: JSON.stringify(mockMessage) } as any);
    }

    await waitFor(() => {
      expect(result.current.lastMessage).toEqual(mockMessage);
    });
  });

  it('handles invalid JSON in messages gracefully', async () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();
    const { result } = renderHook(() => useWebSocket('/ws'));

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    });

    const ws = MockWebSocket.instances[0];
    if (ws.onmessage) {
      ws.onmessage({ data: 'invalid json' } as any);
    }

    expect(consoleErrorSpy).toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });

  it('handles WebSocket errors', async () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();
    const { result } = renderHook(() => useWebSocket('/ws'));

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    });

    const ws = MockWebSocket.instances[0];
    if (ws.onerror) {
      ws.onerror(new Error('Test error') as any);
    }

    expect(consoleErrorSpy).toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });

  it('cleans up on unmount', async () => {
    const { result, unmount } = renderHook(() => useWebSocket('/ws'));

    await waitFor(() => {
      expect(result.current.connected).toBe(true);
    });

    const ws = MockWebSocket.instances[0];
    const closeSpy = jest.spyOn(ws, 'close');

    unmount();

    expect(closeSpy).toHaveBeenCalled();
  });
});

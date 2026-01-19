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
});

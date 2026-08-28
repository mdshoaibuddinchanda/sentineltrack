import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useWebSocket } from "../hooks/useWebSocket";

describe("WebSocket Lifecycle & Stability Tests", () => {
  let createdSockets: any[] = [];
  let originalWebSocket: any;

  class MockWebSocket {
    public url: string;
    public readyState: number = 0; // CONNECTING
    public onopen: (() => void) | null = null;
    public onmessage: ((event: any) => void) | null = null;
    public onclose: (() => void) | null = null;
    public onerror: (() => void) | null = null;
    public send = vi.fn();
    public close = vi.fn().mockImplementation(() => {
      this.readyState = 3; // CLOSED
      if (this.onclose) this.onclose();
    });

    constructor(url: string) {
      this.url = url;
      this.readyState = 0;
      createdSockets.push(this);
      setTimeout(() => {
        if (this.readyState === 0) {
          this.readyState = 1; // OPEN
          if (this.onopen) this.onopen();
        }
      }, 5);
    }
  }

  beforeEach(() => {
    createdSockets = [];
    originalWebSocket = global.WebSocket;
    global.WebSocket = MockWebSocket as any;
    vi.useFakeTimers();
  });

  afterEach(() => {
    global.WebSocket = originalWebSocket;
    vi.useRealTimers();
  });

  it("initial render establishes exactly one WebSocket connection", () => {
    const { result } = renderHook(() => useWebSocket("*"));
    expect(createdSockets.length).toBe(1);
    expect(createdSockets[0].url).toContain("topics=*");
    expect(result.current.status).toBe("CONNECTING");

    act(() => {
      vi.advanceTimersByTime(10);
    });
    expect(result.current.status).toBe("LIVE");
  });

  it("20 harmless component rerenders do not recreate the WebSocket", () => {
    const { rerender } = renderHook(({ topics }) => useWebSocket(topics), {
      initialProps: { topics: ["*"] },
    });

    expect(createdSockets.length).toBe(1);

    // Perform 20 rerenders with new array instances containing identical topic
    for (let i = 0; i < 20; i++) {
      rerender({ topics: ["*"] });
    }

    expect(createdSockets.length).toBe(1);
  });

  it("receiving a WebSocket event updates events without reconnecting", () => {
    const { result } = renderHook(() => useWebSocket("*"));

    act(() => {
      vi.advanceTimersByTime(10);
    });
    expect(createdSockets.length).toBe(1);

    const socket = createdSockets[0];
    const testMsg = {
      event_type: "ALERT_CREATED",
      timestamp: "2026-08-28T12:00:00Z",
      data: { alert_id: "alt_test_01", registration: "GJ01AB1234" },
    };

    act(() => {
      socket.onmessage({ data: JSON.stringify(testMsg) });
    });

    expect(result.current.events.length).toBe(1);
    expect(result.current.events[0].event_type).toBe("ALERT_CREATED");
    expect(createdSockets.length).toBe(1);
  });

  it("actual network close triggers reconnect with backoff", () => {
    const { result } = renderHook(() => useWebSocket("*"));

    act(() => {
      vi.advanceTimersByTime(10);
    });
    expect(createdSockets.length).toBe(1);

    // Simulate unexpected network socket closure
    act(() => {
      const socket = createdSockets[0];
      socket.readyState = 3;
      if (socket.onclose) socket.onclose();
    });

    expect(result.current.status).toBe("OFFLINE");

    // Advance timers for 1st reconnect backoff (1000ms)
    act(() => {
      vi.advanceTimersByTime(1050);
    });

    expect(createdSockets.length).toBe(2);
  });

  it("unmounting hook closes socket cleanly and does not reconnect after timers advance", () => {
    const { unmount } = renderHook(() => useWebSocket("*"));
    expect(createdSockets.length).toBe(1);

    unmount();
    expect(createdSockets[0].close).toHaveBeenCalledTimes(1);

    // Advance fake timers by 60 seconds
    act(() => {
      vi.advanceTimersByTime(60000);
    });

    // No secondary reconnect socket must have been spawned after unmount
    expect(createdSockets.length).toBe(1);
  });
});

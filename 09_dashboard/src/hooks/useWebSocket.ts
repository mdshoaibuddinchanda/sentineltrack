import { useState, useEffect, useRef, useCallback } from "react";
import { WebSocketConnectionStatus, WebSocketEventMessage } from "../types/websocket";

const WS_BASE_URL = import.meta.env.VITE_SENTINEL_WS_URL || "ws://localhost:8000";

export function useWebSocket(topics: string[] | string = "*") {
  const [status, setStatus] = useState<WebSocketConnectionStatus>("CONNECTING");
  const [events, setEvents] = useState<WebSocketEventMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimeoutRef = useRef<any>(null);
  const pingIntervalRef = useRef<any>(null);
  const seenEventIdsRef = useRef<Set<string>>(new Set());

  const topicKey = Array.isArray(topics) ? topics.slice().sort().join(",") : String(topics || "*");

  const shouldReconnectRef = useRef(true);

  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setStatus((prev) => (prev === "LIVE" ? "RECONNECTING" : "CONNECTING"));
    const wsUrl = `${WS_BASE_URL}/ws/events?topics=${encodeURIComponent(topicKey)}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("LIVE");
        reconnectAttemptRef.current = 0;

        // Start ping heartbeat
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 15000);
      };

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed.type === "pong") return;

          const msg = parsed as WebSocketEventMessage;
          const dedupeKey = `${msg.event_type}_${msg.timestamp}_${msg.data?.alert_id || msg.data?.sighting_id || JSON.stringify(msg.data)}`;

          if (seenEventIdsRef.current.has(dedupeKey)) {
            return;
          }
          seenEventIdsRef.current.add(dedupeKey);
          if (seenEventIdsRef.current.size > 1000) {
            seenEventIdsRef.current.clear();
          }

          setEvents((prev) => [msg, ...prev].slice(0, 200));
        } catch (e) {
          console.warn("Error parsing WebSocket message:", e);
        }
      };

      ws.onclose = () => {
        setStatus("OFFLINE");
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        if (!shouldReconnectRef.current) return;

        // Exponential backoff reconnection (1s, 2s, 4s, 8s, max 30s)
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current), 30000);
        reconnectAttemptRef.current += 1;

        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(() => {
          if (shouldReconnectRef.current) {
            connect();
          }
        }, delay);
      };

      ws.onerror = () => {
        setStatus("OFFLINE");
        ws.close();
      };
    } catch {
      setStatus("OFFLINE");
    }
  }, [topicKey]);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();
    return () => {
      shouldReconnectRef.current = false;
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  return { status, events, clearEvents };
}

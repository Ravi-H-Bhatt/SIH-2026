"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1/ws";

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const { token } = useAuth();

  useEffect(() => {
    // The feed carries traveller PII and criminal flags, so the server now
    // requires a JWT. Browsers can't set headers on a WS handshake, so the token
    // travels as a query parameter over wss://.
    if (!token) {
      setIsConnected(false);
      return;
    }

    let ws: WebSocket;

    try {
      ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
        } catch (e) {
          setLastMessage(event.data);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
      };

      ws.onerror = (error) => {
        console.warn("WebSocket error:", error);
        setIsConnected(false);
      };
    } catch (err) {
      console.warn("WebSocket connection failed:", err);
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [token]);

  const sendMessage = (msg: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
  };

  return { isConnected, lastMessage, sendMessage };
}

import { useEffect, useRef, useState } from 'react';
import { store, useAppDispatch, useAppSelector } from '../app/store';
import { fetchWsTicket } from '../app/api';
import { fetchProjects, receiveWebSocketApproval } from '../features/projects/projectsSlice';
import { fetchDashboardData } from '../features/analytics/analyticsSlice';
import { ServerMessage } from '../types';

const HEARTBEAT_MS = 25_000;
const PONG_TIMEOUT_MS = 10_000;
const MAX_BACKOFF_MS = 15_000;
const DASHBOARD_DEBOUNCE_MS = 400;

/**
 * Real-time stream with:
 *  - ticket-based handshake (no JWT in the URL),
 *  - heartbeat: `live` means "the server answered recently", not just "the socket is open",
 *  - reconciliation on every (re)connect so events missed while offline are not lost,
 *  - dashboard refetch driven by analytics_update (sent once rollups are actually rewritten).
 */
export const useWebSocket = () => {
  const dispatch = useAppDispatch();
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated);
  const [live, setLive] = useState<boolean>(false);

  const socketRef = useRef<WebSocket | null>(null);
  const timers = useRef<{ reconnect?: number; heartbeat?: number; pongDeadline?: number; dashboard?: number }>({});
  const retryCountRef = useRef<number>(0);

  useEffect(() => {
    if (!isAuthenticated) {
      setLive(false);
      return;
    }
    let disposed = false;

    const refreshDashboard = () => {
      window.clearTimeout(timers.current.dashboard);
      timers.current.dashboard = window.setTimeout(() => {
        const { fiscalPeriod, selectedPropertyId } = store.getState().analytics;
        dispatch(fetchDashboardData({ fiscalPeriod, propertyId: selectedPropertyId }));
      }, DASHBOARD_DEBOUNCE_MS);
    };
    const refreshProjects = () => dispatch(fetchProjects({ ...store.getState().projects.lastQuery, background: true }));

    const clearHeartbeat = () => {
      window.clearInterval(timers.current.heartbeat);
      window.clearTimeout(timers.current.pongDeadline);
    };

    const scheduleReconnect = () => {
      if (disposed) return;
      const backoff = Math.min(1000 * 2 ** retryCountRef.current, MAX_BACKOFF_MS);
      retryCountRef.current += 1;
      timers.current.reconnect = window.setTimeout(connect, backoff);
    };

    const connect = async () => {
      if (disposed) return;
      let ticket: string;
      try {
        ticket = await fetchWsTicket();
      } catch {
        scheduleReconnect(); // a 401 here logs the user out via the API interceptor
        return;
      }
      if (disposed) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsBase = import.meta.env.VITE_WS_URL || `${protocol}//${window.location.host}/ws/approvals/`;
      const ws = new WebSocket(`${wsBase}${wsBase.includes('?') ? '&' : '?'}ticket=${encodeURIComponent(ticket)}`);
      socketRef.current = ws;

      ws.onopen = () => {
        retryCountRef.current = 0;
        setLive(true);
        // Reconcile anything missed while disconnected.
        refreshProjects();
        refreshDashboard();
        timers.current.heartbeat = window.setInterval(() => {
          if (ws.readyState !== WebSocket.OPEN) return;
          ws.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
          window.clearTimeout(timers.current.pongDeadline);
          timers.current.pongDeadline = window.setTimeout(() => {
            setLive(false);
            ws.close(); // dead stream: reconnect
          }, PONG_TIMEOUT_MS);
        }, HEARTBEAT_MS);
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        let msg: ServerMessage;
        try {
          msg = JSON.parse(event.data) as ServerMessage;
        } catch (e) {
          console.error('Failed to parse WebSocket message', e);
          return;
        }
        switch (msg.type) {
          case 'pong':
            window.clearTimeout(timers.current.pongDeadline);
            setLive(true);
            break;
          case 'approval_update':
            dispatch(receiveWebSocketApproval(msg.data));
            refreshProjects(); // keep counts/rows authoritative, with the user's page & filters
            break;
          case 'analytics_update':
            refreshDashboard(); // rollups for this property were just rewritten
            break;
          default:
            break;
        }
      };

      ws.onclose = () => {
        clearHeartbeat();
        setLive(false);
        if (socketRef.current === ws) socketRef.current = null;
        scheduleReconnect();
      };

      ws.onerror = () => {
        // onclose follows and handles reconnection
      };
    };

    connect();

    return () => {
      disposed = true;
      clearHeartbeat();
      window.clearTimeout(timers.current.reconnect);
      window.clearTimeout(timers.current.dashboard);
      socketRef.current?.close();
      socketRef.current = null;
      setLive(false);
    };
  }, [isAuthenticated, dispatch]);

  return { connected: live };
};

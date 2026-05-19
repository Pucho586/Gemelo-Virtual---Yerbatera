import { useEffect, useRef, useState } from 'react';
import { api, wsUrl } from './api';

/**
 * Mantiene `state` actualizado via WebSocket con fallback a polling.
 * También conserva una serie de historial local para los gráficos.
 */
export function useLiveState({ historyLength = 180 } = {}) {
  const [state, setState] = useState(null);
  const [connected, setConnected] = useState(false);
  const [series, setSeries] = useState([]); // array of snapshots
  const wsRef = useRef(null);
  const seriesRef = useRef([]);

  useEffect(() => {
    let mounted = true;
    let pollTimer = null;
    let reconnectTimer = null;

    const pushSnapshot = (s) => {
      if (!s) return;
      const next = [...seriesRef.current, s];
      if (next.length > historyLength) next.shift();
      seriesRef.current = next;
      setSeries(next);
      setState(s);
    };

    // Boot with REST + history
    const boot = async () => {
      try {
        const [hist, st] = await Promise.all([api.getHistory(historyLength), api.getState()]);
        if (!mounted) return;
        seriesRef.current = hist.slice(-historyLength);
        setSeries(seriesRef.current);
        setState(st);
      } catch (e) {
        console.warn('initial fetch failed', e);
      }
    };

    const connect = () => {
      try {
        const ws = new WebSocket(wsUrl());
        wsRef.current = ws;
        ws.onopen = () => mounted && setConnected(true);
        ws.onclose = () => {
          if (!mounted) return;
          setConnected(false);
          // Reintento + fallback polling
          if (!pollTimer) startPolling();
          reconnectTimer = setTimeout(connect, 4000);
        };
        ws.onerror = () => {
          try { ws.close(); } catch (e) { /* ignore */ }
        };
        ws.onmessage = (ev) => {
          try {
            const s = JSON.parse(ev.data);
            pushSnapshot(s);
          } catch (e) { /* ignore parse errors */ }
        };
      } catch (e) {
        startPolling();
      }
    };

    const startPolling = () => {
      if (pollTimer) return;
      pollTimer = setInterval(async () => {
        try {
          const s = await api.getState();
          pushSnapshot(s);
        } catch (e) { /* ignore */ }
      }, 2000);
    };

    boot().then(connect);

    return () => {
      mounted = false;
      if (wsRef.current) try { wsRef.current.close(); } catch (e) { /* ignore */ }
      if (pollTimer) clearInterval(pollTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [historyLength]);

  return { state, connected, series };
}

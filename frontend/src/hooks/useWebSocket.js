import { useEffect, useRef } from 'react';

/**
 * Opens a WebSocket to `url`, calling `onMessage(parsedData)` for every
 * message.  Auto-reconnects after 3 s on close or error.
 */
export function useWebSocket(url, onMessage) {
  const cbRef = useRef(onMessage);
  cbRef.current = onMessage;

  useEffect(() => {
    let ws = null;
    let timer = null;
    let destroyed = false;

    function connect() {
      if (destroyed) return;
      ws = new WebSocket(url);

      ws.onmessage = (e) => {
        try { cbRef.current(JSON.parse(e.data)); } catch {}
      };

      ws.onclose = () => {
        if (!destroyed) timer = setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      destroyed = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, [url]);
}

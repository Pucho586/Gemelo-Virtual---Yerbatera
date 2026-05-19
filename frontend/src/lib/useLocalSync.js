/* useLocalSync: combina estado local controlado con sync desde backend,
 * evitando que un tick de WebSocket "pise" lo que el usuario acaba de cambiar.
 *
 * Patrón:
 *   const [valor, setValor, syncedFromBackend] = useLocalSync(remoteValue, [deps]);
 *   onClick: setValor(newValue) + apply POST  ← local cambia, ignora backend X ms
 *
 * El hook bloquea la sincronización entrante durante `freezeMs` después de un setValor local.
 */
import { useEffect, useRef, useState } from 'react';

export function useLocalSync(remoteValue, freezeMs = 2500) {
  const [value, setValue] = useState(remoteValue);
  const lastEditRef = useRef(0);

  // Sync desde backend SOLO si pasó suficiente tiempo desde la última edición local
  useEffect(() => {
    if (Date.now() - lastEditRef.current < freezeMs) return;
    setValue(remoteValue);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remoteValue]);

  const setLocal = (v) => {
    lastEditRef.current = Date.now();
    setValue(v);
  };

  return [value, setLocal];
}

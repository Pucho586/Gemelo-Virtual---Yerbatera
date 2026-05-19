/* WeatherControl: badge clickable que muestra T/HR ambient + permite override manual.
 * Util cuando Open-Meteo está rate-limited o el usuario quiere simular otro clima. */
import React, { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';
import { useAuth, isAdmin } from '../lib/auth';
import { CloudSun, CloudSlash, CloudArrowDown } from '@phosphor-icons/react';

export default function WeatherControl({ ambient, weatherStatus }) {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [open, setOpen] = useState(false);
  const [city, setCity] = useState(ambient?.city || '');
  const [tManual, setTManual] = useState(ambient?.temp ?? 24);
  const [hManual, setHManual] = useState(ambient?.humidity ?? 70);
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [lastError, setLastError] = useState('');
  const rootRef = useRef(null);

  useEffect(() => {
    if (ambient?.city) setCity(ambient.city);
    if (ambient?.temp != null) setTManual(ambient.temp);
    if (ambient?.humidity != null) setHManual(ambient.humidity);
  }, [ambient?.city, ambient?.temp, ambient?.humidity]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const fresh = ambient?.updated_at != null;
  const tone = fresh ? 'text-emerald-300 border-emerald-500/30' : 'text-amber-300 border-amber-500/30';
  const Icon = fresh ? CloudSun : CloudSlash;

  const onSearchCity = async () => {
    if (!search.trim()) return;
    setBusy(true);
    try {
      const r = await api.searchCity(search.trim());
      setSearchResults(r || []);
    } catch (e) { setLastError(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const selectCity = async (item) => {
    setBusy(true); setLastError('');
    try {
      const r = await api.setWeatherLocation({ latitude: item.latitude, longitude: item.longitude, city: item.label });
      setCity(item.label);
      setSearchResults([]);
      setSearch('');
      if (!r.current?.temperature) {
        setLastError('Open-Meteo no devolvió datos (rate limit). Usá override manual.');
      }
    } catch (e) { setLastError(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const applyManual = async () => {
    setBusy(true); setLastError('');
    try {
      await api.setWeatherManual({ temperature: parseFloat(tManual), humidity: parseFloat(hManual) });
    } catch (e) { setLastError(String(e.message || e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="relative" ref={rootRef}>
      <button
        data-testid="weather-control-btn"
        onClick={() => setOpen(o => !o)}
        className={`inline-flex items-center gap-1.5 px-2 py-1 text-xs font-mono border transition-colors ${tone}`}
        title={fresh ? `Clima en vivo · ${city}` : 'Clima sin actualizar (Open-Meteo caído o nunca refrescado)'}
      >
        <Icon size={12} weight="duotone" />
        {ambient?.temp != null ? `${ambient.temp.toFixed(0)}°/${(ambient.humidity ?? 0).toFixed(0)}%` : 'Clima'}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 border min-w-[340px] p-3" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }} data-testid="weather-panel">
          <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">Clima ambiente</div>
          <div className="text-sm text-slate-200 mb-2">
            <div className="font-mono">{ambient?.city || 'Posadas, Misiones'}</div>
            <div className="text-[11px] text-slate-500">
              {fresh
                ? `Última actualización: ${new Date(ambient.updated_at).toLocaleTimeString()}`
                : 'Sin datos en vivo. Open-Meteo puede estar rate-limited.'}
            </div>
            {ambient?.source === 'fallback-seasonal' && (
              <div className="text-[10px] text-amber-300 font-mono mt-1" data-testid="weather-fallback-indicator">
                ⚠ Clima estacional sintético (Open-Meteo no responde)
              </div>
            )}
            {ambient?.source === 'manual' && (
              <div className="text-[10px] text-cyan-300 font-mono mt-1">
                ✓ Override manual aplicado
              </div>
            )}
            {ambient?.source === 'open-meteo' && (
              <div className="text-[10px] text-emerald-300 font-mono mt-1">
                ● Datos en vivo de Open-Meteo
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="border p-2" style={{ borderColor: 'var(--border)' }}>
              <div className="text-[10px] font-mono text-slate-500">T ambiente</div>
              <div className="text-lg font-mono text-amber-300" data-testid="weather-amb-t">{(ambient?.temp ?? 0).toFixed(1)}°C</div>
            </div>
            <div className="border p-2" style={{ borderColor: 'var(--border)' }}>
              <div className="text-[10px] font-mono text-slate-500">HR ambiente</div>
              <div className="text-lg font-mono text-blue-300" data-testid="weather-amb-h">{(ambient?.humidity ?? 0).toFixed(0)}%</div>
            </div>
          </div>

          {admin && (
            <>
              <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">Buscar ciudad</div>
                <div className="flex gap-1">
                  <input
                    data-testid="weather-search-input"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && onSearchCity()}
                    placeholder="Posadas, Salta, Madrid…"
                    className="field flex-1 text-xs"
                  />
                  <button data-testid="weather-search-btn" onClick={onSearchCity} disabled={busy} className="px-2 py-1 text-xs font-mono border border-amber-500/40 text-amber-300 hover:bg-amber-500/15 disabled:opacity-50">Buscar</button>
                </div>
                {searchResults.length > 0 && (
                  <div className="mt-1 border max-h-32 overflow-y-auto" style={{ borderColor: 'var(--border)' }}>
                    {searchResults.map((r, i) => (
                      <button key={i} data-testid={`weather-result-${i}`} onClick={() => selectCity(r)} className="w-full text-left px-2 py-1 text-xs hover:bg-amber-500/10 text-slate-200">
                        {r.label} ({r.latitude.toFixed(2)}, {r.longitude.toFixed(2)})
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">Override manual</div>
                <div className="text-[10px] text-slate-500 mb-2">Si Open-Meteo está caído, fijá T y HR a mano. El simulador los usará como ambiente.</div>
                <div className="grid grid-cols-2 gap-2">
                  <label className="flex flex-col gap-1">
                    <span className="text-[10px] font-mono text-slate-500">T °C</span>
                    <input data-testid="weather-manual-t" type="number" value={tManual} onChange={(e) => setTManual(e.target.value)} step="0.5" className="field text-xs" />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="text-[10px] font-mono text-slate-500">HR %</span>
                    <input data-testid="weather-manual-h" type="number" value={hManual} onChange={(e) => setHManual(e.target.value)} step="1" className="field text-xs" />
                  </label>
                </div>
                <button data-testid="weather-manual-apply" onClick={applyManual} disabled={busy} className="mt-2 w-full px-2 py-1 text-xs font-mono border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/15 disabled:opacity-50 inline-flex items-center justify-center gap-1">
                  <CloudArrowDown size={12} /> Aplicar manual
                </button>
              </div>
            </>
          )}

          {lastError && <div className="mt-2 text-[10px] text-red-400 font-mono">{lastError}</div>}
        </div>
      )}
    </div>
  );
}

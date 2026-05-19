/* SpeedControl: factor de aceleración global del simulador.
 * Permite al operador comprimir el tiempo (ej. ver 1 hora real en 1 minuto).
 * Persiste vía /api/config { simulacion: { aceleracion } }. */
import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Timer } from '@phosphor-icons/react';

const PRESETS = [
  { label: '1×',   value: 1,      desc: 'Real (1 s real = 1 s sim)' },
  { label: '60×',  value: 60,     desc: '1 s real = 1 min sim' },
  { label: '1h/s', value: 3600,   desc: '1 s real = 1 h sim' },
  { label: '1d/s', value: 86400,  desc: '1 s real = 1 día sim' },
];

export default function SpeedControl({ compact = false }) {
  const [accel, setAccel] = useState(60);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.getConfig().then(cfg => {
      const a = cfg?.simulacion?.aceleracion;
      if (a) setAccel(Number(a));
    }).catch(() => {});
  }, []);

  const setPreset = async (v) => {
    setAccel(v);
    setOpen(false);
    try {
      await api.patchConfig({ simulacion: { aceleracion: v } });
    } catch (e) { /* admin-only; UI feedback no es crítico */ }
  };

  const currentLabel = (() => {
    if (accel <= 1) return '1×';
    if (accel < 60) return `${accel}×`;
    if (accel < 3600) return `${Math.round(accel / 60)}m/s`;
    if (accel < 86400) return `${Math.round(accel / 3600)}h/s`;
    return `${Math.round(accel / 86400)}d/s`;
  })();

  return (
    <div className="relative" data-testid="speed-control">
      <button
        onClick={() => setOpen(o => !o)}
        className="inline-flex items-center gap-1.5 text-xs font-mono text-amber-300 hover:text-amber-200 border border-amber-500/40 px-2 py-1"
        data-testid="speed-control-btn"
        title="Velocidad de simulación (compresión de tiempo)"
      >
        <Timer size={12} weight="duotone" /> {currentLabel}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-40 border min-w-[220px]" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }} data-testid="speed-control-menu">
          <div className="px-3 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Velocidad simulación</div>
          </div>
          {PRESETS.map(p => (
            <button
              key={p.value}
              data-testid={`speed-preset-${p.value}`}
              onClick={() => setPreset(p.value)}
              className={`w-full text-left px-3 py-2 hover:bg-amber-500/10 transition-colors ${accel === p.value ? 'bg-amber-500/15' : ''}`}
            >
              <div className={`text-xs font-mono ${accel === p.value ? 'text-amber-300' : 'text-slate-200'}`}>{p.label}</div>
              <div className="text-[10px] text-slate-500">{p.desc}</div>
            </button>
          ))}
          <div className="px-3 py-2 border-t text-[10px] text-slate-500 font-mono" style={{ borderColor: 'var(--border)' }}>
            Acel ×{accel}
          </div>
        </div>
      )}
    </div>
  );
}

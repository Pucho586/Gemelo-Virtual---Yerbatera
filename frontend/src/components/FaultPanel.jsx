/* FaultPanel: inyección de fallas por etapa.
 * Renderiza toggles para cada falla disponible, llamando onApply(patch) con
 * el body que /api/{etapa} acepta. Las fallas se exponen también a Modbus/OPC UA. */
import React from 'react';
import { Toggle } from './UI';
import { WarningOctagon } from '@phosphor-icons/react';

export default function FaultPanel({ title = 'Inyección de fallas', faults = {}, defs = [], onApply, testidBase = 'fault' }) {
  // defs: [{ key, label, hint }]
  const anyActive = defs.some(d => !!faults?.[d.key]);
  return (
    <div className="border" style={{ borderColor: anyActive ? 'var(--red, #EF4444)' : 'var(--border)', background: 'var(--surface)' }} data-testid={`${testidBase}-panel`}>
      <div className="flex items-center justify-between px-4 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <WarningOctagon size={14} weight={anyActive ? 'fill' : 'duotone'} className={anyActive ? 'text-red-400' : 'text-slate-400'} />
          <span className={`text-[11px] font-mono uppercase tracking-wider ${anyActive ? 'text-red-300' : 'text-slate-400'}`}>{title}</span>
        </div>
        {anyActive && <span className="text-[10px] font-mono text-red-400">ACTIVA</span>}
      </div>
      <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        {defs.map(({ key, label, hint }) => {
          const on = !!faults?.[key];
          return (
            <div key={key} className="flex items-start justify-between gap-3 p-2 border" style={{ borderColor: on ? 'rgba(239,68,68,0.4)' : 'var(--border)' }}>
              <div className="flex-1 min-w-0">
                <div className={`text-xs font-mono ${on ? 'text-red-300' : 'text-slate-200'}`}>{label}</div>
                {hint && <div className="text-[10px] text-slate-500 mt-0.5 leading-tight">{hint}</div>}
              </div>
              <Toggle
                testid={`${testidBase}-${key}`}
                value={on}
                onChange={(v) => onApply({ [key]: v })}
                label={on ? 'ON' : 'OFF'}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* PidPanel: controla un PID interno (Kp/Ki/Kd + enable + reset).
 * El PID toma como entrada el SP de la etapa y manipula una variable física
 * (vel.chip, posición calefactor, vel.aire, caudal vapor, rpm molino).
 *
 * Cuando el PID está OFF, el operador (o PLC externo) maneja la manipulada.
 * Cuando está ON, el PID la calcula automáticamente para llegar al SP. */
import React, { useState } from 'react';
import { Robot } from '@phosphor-icons/react';
import { Toggle } from './UI';

export default function PidPanel({ title = 'Controlador PID interno', pid, onApply, manipulada, testidBase = 'pid' }) {
  const [kp, setKp] = useState(pid?.kp ?? 1.0);
  const [ki, setKi] = useState(pid?.ki ?? 0.0);
  const [kd, setKd] = useState(pid?.kd ?? 0.0);
  const enabled = !!pid?.enabled;
  const lastOut = pid?.last_output ?? 0;
  const integral = pid?.integral ?? 0;

  React.useEffect(() => {
    if (pid) { setKp(pid.kp); setKi(pid.ki); setKd(pid.kd); }
  }, [pid?.kp, pid?.ki, pid?.kd]);

  const submit = (patch) => onApply(patch);

  return (
    <div className="border" style={{ borderColor: enabled ? 'rgba(34,197,94,0.3)' : 'var(--border)', background: 'var(--surface)' }} data-testid={`${testidBase}-panel`}>
      <div className="flex items-center justify-between px-3 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <Robot size={14} weight="duotone" className={enabled ? 'text-emerald-400' : 'text-slate-500'} />
          <span className="text-[11px] font-mono uppercase tracking-wider text-slate-300">{title}</span>
          {enabled && <span className="text-[10px] font-mono text-emerald-300">AUTO</span>}
          {!enabled && <span className="text-[10px] font-mono text-amber-300">MANUAL</span>}
        </div>
        <Toggle testid={`${testidBase}-enabled`} value={enabled} onChange={(v) => submit({ enabled: v, reset: v })} label={enabled ? 'ON' : 'OFF'} />
      </div>
      <div className="p-3 space-y-2">
        <div className="text-[10px] text-slate-500 leading-tight">
          {enabled
            ? `El PID ajusta automáticamente la manipulada (${manipulada || 'salida'}) para llegar al SP. Probá tunar Kp/Ki para ver overshoot/settling.`
            : `Operador / PLC controla la manipulada (${manipulada || 'salida'}) manualmente. Activá AUTO para que el PID interno la calcule.`}
        </div>
        <div className="grid grid-cols-3 gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-mono text-slate-500">Kp</span>
            <input data-testid={`${testidBase}-kp`} type="number" value={kp} step="0.05" onChange={(e) => setKp(parseFloat(e.target.value))} onBlur={() => submit({ kp })} className="field text-xs" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-mono text-slate-500">Ki</span>
            <input data-testid={`${testidBase}-ki`} type="number" value={ki} step="0.01" onChange={(e) => setKi(parseFloat(e.target.value))} onBlur={() => submit({ ki })} className="field text-xs" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-mono text-slate-500">Kd</span>
            <input data-testid={`${testidBase}-kd`} type="number" value={kd} step="0.01" onChange={(e) => setKd(parseFloat(e.target.value))} onBlur={() => submit({ kd })} className="field text-xs" />
          </label>
        </div>
        <div className="grid grid-cols-2 gap-2 text-[11px] font-mono pt-1">
          <div className="text-slate-500">Out: <span className="text-emerald-300">{lastOut.toFixed(2)}</span></div>
          <div className="text-slate-500">Σerr: <span className="text-slate-300">{integral.toFixed(2)}</span></div>
        </div>
        <button data-testid={`${testidBase}-reset`} onClick={() => submit({ reset: true })} className="w-full text-[10px] font-mono text-slate-400 hover:text-amber-300 border border-slate-700 py-1">Reset integral</button>
      </div>
    </div>
  );
}

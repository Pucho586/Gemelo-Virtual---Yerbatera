import React from 'react';
import { Card, Btn, NumberInput } from './UI';
import { Hand, Lightning, Sliders, Plugs } from '@phosphor-icons/react';

/*
 * Panel de "Sistema de control" por etapa.
 * Deja elegir explícitamente CÓMO se controla la variable manipulada (MV):
 *   - manual   : el operador la fija a mano
 *   - onoff    : controlador todo-o-nada con histéresis (bang-bang)
 *   - pid      : PID interno persigue el SP
 *   - external : la MV la escribe un PLC externo por Modbus/OPC UA/MQTT (modo twin)
 * Muestra un badge claro con el modo activo y sólo los parámetros de ese modo.
 */
const MODES = [
  { id: 'manual', label: 'Manual', Icon: Hand, desc: 'El operador fija la MV a mano.' },
  { id: 'onoff', label: 'ON/OFF', Icon: Lightning, desc: 'Todo-o-nada con histéresis (termostato).' },
  { id: 'pid', label: 'PID', Icon: Sliders, desc: 'El PID interno persigue el setpoint.' },
  { id: 'external', label: 'PLC externo', Icon: Plugs, desc: 'La MV la escribe tu PLC por Modbus/OPC UA/MQTT.' },
];

export default function ControlSystemPanel({
  stageLabel, mvLabel, spLabel, spValue, spUnit = '',
  control_mode = 'manual', pid = {}, onoff = {}, onApply, admin = true, testidBase = 'ctrl',
  applyKeys = { mode: 'control_mode', pid: 'pid', onoff: 'onoff' },
}) {
  const mode = control_mode || 'manual';
  const meta = MODES.find(m => m.id === mode) || MODES[0];

  const setMode = (id) => { if (admin) onApply({ [applyKeys.mode]: id }); };
  const patchOnoff = (k, v) => onApply({ [applyKeys.onoff]: { [k]: v } });
  const patchPid = (k, v) => onApply({ [applyKeys.pid]: { [k]: v } });

  return (
    <Card className="p-5" testid={`${testidBase}-card`}>
      <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
        <div className="flex items-center gap-2.5">
          <meta.Icon size={18} weight="duotone" className="text-amber-300" />
          <div>
            <h3 className="font-display text-base font-medium text-slate-100">Sistema de control · {stageLabel}</h3>
            <p className="text-[11px] text-slate-500">Controla <span className="text-slate-300">{mvLabel}</span> para llegar al SP{spLabel ? ` de ${spLabel}` : ''}</p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider border bg-amber-300/10 text-amber-200 border-amber-300/40" data-testid={`${testidBase}-badge`}>
          <meta.Icon size={13} weight="duotone" /> {meta.label}
        </span>
      </div>

      {/* Selector de modo */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
        {MODES.map(m => {
          const on = mode === m.id;
          return (
            <button
              key={m.id}
              data-testid={`${testidBase}-mode-${m.id}`}
              onClick={() => setMode(m.id)}
              disabled={!admin}
              title={m.desc}
              className={`flex flex-col items-start gap-1 px-3 py-2.5 border text-left transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${on ? 'bg-amber-300/10 border-amber-300/40 text-amber-100' : 'border-[#232A26] text-slate-400 hover:text-slate-200 hover:border-slate-600'}`}
            >
              <span className="inline-flex items-center gap-1.5 text-sm font-medium"><m.Icon size={14} weight={on ? 'fill' : 'regular'} /> {m.label}</span>
              <span className="text-[10px] leading-tight text-slate-500">{m.desc}</span>
            </button>
          );
        })}
      </div>

      {/* SP de referencia */}
      {spLabel && (
        <div className="flex items-center justify-between text-xs font-mono border-t pt-3 mb-1" style={{ borderColor: 'var(--border)' }}>
          <span className="text-slate-500 uppercase tracking-wider">Setpoint ({spLabel})</span>
          <span className="text-amber-300">{spValue != null ? `${spValue}${spUnit}` : 'dinámico'}</span>
        </div>
      )}

      {/* Parámetros según el modo */}
      {mode === 'manual' && (
        <p className="text-xs text-slate-400 mt-3 leading-relaxed">
          En <b className="text-slate-200">Manual</b>, la variable manipulada (<span className="text-amber-300">{mvLabel}</span>) la fijás vos con los controles de la etapa. Ningún controlador la toca.
        </p>
      )}

      {mode === 'onoff' && (
        <div className="mt-3 space-y-3">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-slate-500 uppercase tracking-wider">Estado del actuador</span>
            <span className={onoff.state_on ? 'text-green-400' : 'text-slate-500'}>{onoff.state_on ? '● ENCENDIDO' : '○ apagado'} · MV={onoff.last_output ?? '–'}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <NumberInput testid={`${testidBase}-onoff-hyst`} label="Histéresis" unit="banda muerta" value={onoff.hysteresis ?? 5} onChange={(v) => patchOnoff('hysteresis', v)} min={0} max={100} step={1} />
            <NumberInput testid={`${testidBase}-onoff-high`} label="MV encendido" value={onoff.out_high ?? 60} onChange={(v) => patchOnoff('out_high', v)} min={0} max={200} step={1} />
            <NumberInput testid={`${testidBase}-onoff-low`} label="MV apagado" value={onoff.out_low ?? 0} onChange={(v) => patchOnoff('out_low', v)} min={0} max={200} step={1} />
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Enciende <span className="text-amber-300">{mvLabel}</span> a <b>MV encendido</b> cuando la medida cae por debajo del SP menos media histéresis, y apaga a <b>MV apagado</b> cuando la supera. Sin sintonía: control clásico de termostato.
          </p>
        </div>
      )}

      {mode === 'pid' && (
        <div className="mt-3 space-y-3">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-slate-500 uppercase tracking-wider">Salida PID (MV)</span>
            <span className="text-amber-300">{pid.last_output ?? '–'} · integral {pid.integral ?? 0}</span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <NumberInput testid={`${testidBase}-pid-kp`} label="Kp" value={pid.kp ?? 1} onChange={(v) => patchPid('kp', v)} step={0.05} />
            <NumberInput testid={`${testidBase}-pid-ki`} label="Ki" value={pid.ki ?? 0} onChange={(v) => patchPid('ki', v)} step={0.005} />
            <NumberInput testid={`${testidBase}-pid-kd`} label="Kd" value={pid.kd ?? 0} onChange={(v) => patchPid('kd', v)} step={0.005} />
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">Ajustá Kp/Ki/Kd para que <span className="text-amber-300">{mvLabel}</span> lleve la medida al SP sin sobrepico. Anti-windup activado.</p>
        </div>
      )}

      {mode === 'external' && (
        <div className="mt-3 border border-blue-500/25 bg-blue-500/5 p-3 rounded">
          <p className="text-sm text-slate-200 mb-1">Control desde <b className="text-blue-300">PLC externo</b> (modo Gemelo / twin)</p>
          <p className="text-[12px] text-slate-400 leading-relaxed">
            Tu programa de PLC escribe <span className="text-amber-300">{mvLabel}</span> por Modbus / OPC UA / MQTT y la simulación responde con la física real, como si la planta estuviese funcionando. Poné el modo del gemelo en <b className="text-amber-300">Gemelo</b> (header) y configurá la fuente en <b className="text-amber-300">Integración → Industria 4.0</b>. El direccionamiento de cada variable está en <b className="text-amber-300">Integración → Protocolos</b>.
          </p>
        </div>
      )}

      {!admin && <p className="text-[11px] text-slate-500 font-mono mt-3">Cambiar el sistema de control requiere admin.</p>}
    </Card>
  );
}

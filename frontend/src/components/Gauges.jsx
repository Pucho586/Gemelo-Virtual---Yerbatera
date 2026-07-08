import React from 'react';

/*
 * Visualizaciones intuitivas reutilizables.
 * Objetivo: que un operario entienda de un vistazo si una variable está
 * OK (verde), en alerta (ámbar) o crítica (rojo), sin leer el número.
 */

// -- Zonas de operación --------------------------------------------------
// zones: [{ upTo: number, color: string, label?: string }, ...] ordenadas.
// El último tramo cubre hasta `max`. Devuelve la zona donde cae `value`.
export function zoneFor(value, zones, max) {
  if (!zones || zones.length === 0) return null;
  for (const z of zones) {
    if (value <= z.upTo) return z;
  }
  return zones[zones.length - 1];
}

const OK = 'var(--green)';
const WARN = 'var(--amber)';
const BAD = 'var(--red)';

// Estado semántico legible a partir del color de zona.
function statusLabel(color) {
  if (color === BAD || color === '#EF4444') return { text: 'Crítico', cls: 'text-red-400' };
  if (color === WARN || color === '#FCD34D') return { text: 'Alerta', cls: 'text-amber-400' };
  return { text: 'Óptimo', cls: 'text-green-400' };
}

function polar(cx, cy, r, angleDeg) {
  const a = (angleDeg - 90) * (Math.PI / 180);
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

// Arco de 240° (de -120° a +120°), muy legible.
function arcPath(cx, cy, r, startDeg, endDeg) {
  const start = polar(cx, cy, r, startDeg);
  const end = polar(cx, cy, r, endDeg);
  const large = Math.abs(endDeg - startDeg) > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${large} 1 ${end.x} ${end.y}`;
}

/*
 * Gauge radial con zonas de color y marca de objetivo (target).
 * props:
 *   value, min, max, unit, label
 *   zones   -> pinta el anillo por tramos y decide el color/estado del valor
 *   target  -> tick del setpoint objetivo
 */
export function Gauge({
  value, min = 0, max = 100, unit = '', label, zones, target,
  size = 168, testid,
}) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 14;
  const START = -120;
  const END = 120;
  const span = END - START;

  const clamp = (v) => Math.max(min, Math.min(max, v));
  const toAngle = (v) => START + ((clamp(v) - min) / (max - min)) * span;

  const v = typeof value === 'number' && !isNaN(value) ? value : min;
  const valAngle = toAngle(v);
  const activeZone = zoneFor(v, zones, max);
  const valColor = activeZone?.color || OK;
  const status = statusLabel(valColor);

  // Segmentos de color de fondo (zonas de operación)
  const segments = [];
  if (zones && zones.length) {
    let prev = min;
    for (const z of zones) {
      const a0 = toAngle(prev);
      const a1 = toAngle(Math.min(z.upTo, max));
      if (a1 > a0) segments.push({ d: arcPath(cx, cy, r, a0, a1), color: z.color });
      prev = z.upTo;
    }
  }

  const tip = polar(cx, cy, r, valAngle);
  const targetTick = target != null
    ? { a: polar(cx, cy, r + 6, toAngle(target)), b: polar(cx, cy, r - 6, toAngle(target)) }
    : null;

  return (
    <div className="flex flex-col items-center" data-testid={testid}>
      <svg width={size} height={size * 0.82} viewBox={`0 0 ${size} ${size * 0.82}`}>
        {/* Track de fondo */}
        <path d={arcPath(cx, cy, r, START, END)} fill="none" stroke="var(--surface-2)" strokeWidth={10} strokeLinecap="round" />
        {/* Zonas de color (tenues) */}
        {segments.map((s, i) => (
          <path key={i} d={s.d} fill="none" stroke={s.color} strokeWidth={10} strokeLinecap="butt" opacity={0.28} />
        ))}
        {/* Arco activo hasta el valor */}
        <path d={arcPath(cx, cy, r, START, valAngle)} fill="none" stroke={valColor} strokeWidth={10} strokeLinecap="round" />
        {/* Marca de objetivo */}
        {targetTick && (
          <line x1={targetTick.a.x} y1={targetTick.a.y} x2={targetTick.b.x} y2={targetTick.b.y} stroke="var(--text)" strokeWidth={2} />
        )}
        {/* Punta del valor */}
        <circle cx={tip.x} cy={tip.y} r={5} fill={valColor} stroke="var(--surface)" strokeWidth={2} />
        {/* Valor central */}
        <text x={cx} y={cy - 2} textAnchor="middle" fontFamily="JetBrains Mono" fontSize={size * 0.19} fontWeight="300" fill="var(--text)">
          {typeof value === 'number' && !isNaN(value) ? value.toFixed(value < 10 ? 1 : 0) : '–'}
        </text>
        <text x={cx} y={cy + size * 0.13} textAnchor="middle" fontFamily="JetBrains Mono" fontSize={size * 0.08} fill="var(--text-3)">
          {unit}
        </text>
      </svg>
      <div className="flex items-center gap-2 -mt-1">
        <span className="text-[11px] font-medium text-slate-300">{label}</span>
        <span className={`text-[10px] font-mono uppercase tracking-wider ${status.cls}`}>{status.text}</span>
      </div>
      {target != null && (
        <span className="text-[10px] font-mono text-slate-500 mt-0.5">objetivo {target}{unit}</span>
      )}
    </div>
  );
}

/*
 * Barra horizontal con zonas de color y marcador de objetivo.
 * Alternativa compacta al gauge para grillas densas.
 */
export function BarGauge({ value, min = 0, max = 100, unit = '', label, zones, target, testid }) {
  const pct = (v) => Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100));
  const v = typeof value === 'number' && !isNaN(value) ? value : min;
  const zone = zoneFor(v, zones, max);
  const color = zone?.color || OK;
  const status = statusLabel(color);

  return (
    <div data-testid={testid} className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between">
        <span className="text-[11px] text-slate-400">{label}</span>
        <span className="font-mono text-sm" style={{ color }}>
          {typeof value === 'number' ? value.toFixed(value < 10 ? 1 : 0) : '–'}
          <span className="text-slate-500 text-xs ml-0.5">{unit}</span>
        </span>
      </div>
      <div className="relative h-2 rounded-full overflow-hidden" style={{ background: 'var(--surface-2)' }}>
        {/* zonas tenues de fondo */}
        {zones && zones.map((z, i) => {
          const prev = i === 0 ? min : zones[i - 1].upTo;
          const left = pct(prev);
          const w = pct(Math.min(z.upTo, max)) - left;
          return <div key={i} className="absolute top-0 h-full" style={{ left: `${left}%`, width: `${w}%`, background: z.color, opacity: 0.22 }} />;
        })}
        {/* relleno del valor */}
        <div className="absolute top-0 left-0 h-full rounded-full transition-all" style={{ width: `${pct(v)}%`, background: color }} />
        {/* objetivo */}
        {target != null && (
          <div className="absolute top-[-2px] h-3 w-0.5 bg-slate-100" style={{ left: `${pct(target)}%` }} />
        )}
      </div>
      <span className={`text-[9px] font-mono uppercase tracking-wider ${status.cls}`}>{status.text}</span>
    </div>
  );
}

/*
 * KPI semántico: número grande que cambia de color según zonas,
 * con etiqueta de estado y sparkline opcional.
 */
export function StatKpi({ label, value, unit, zones, max, Icon, spark, testid }) {
  const v = typeof value === 'number' ? value : NaN;
  const zone = !isNaN(v) ? zoneFor(v, zones, max) : null;
  const color = zone?.color || 'var(--text)';
  const status = zones ? statusLabel(color) : null;
  return (
    <div data-testid={testid} className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        {Icon && <Icon size={15} style={{ color }} weight="duotone" />}
        <span className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</span>
        {status && <span className={`ml-auto text-[10px] font-mono uppercase tracking-wider ${status.cls}`}>{status.text}</span>}
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="font-mono font-light text-3xl sm:text-4xl tracking-tight" style={{ color }}>
          {!isNaN(v) ? v.toFixed(v < 10 ? 1 : 0) : '–'}
        </span>
        {unit && <span className="font-mono text-sm text-slate-500">{unit}</span>}
      </div>
      {spark}
    </div>
  );
}

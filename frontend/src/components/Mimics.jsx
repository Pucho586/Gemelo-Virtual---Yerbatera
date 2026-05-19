/* Mímicos: SVG animados estilo SCADA + P&ID */
import React from 'react';

const C = {
  bg: '#0A0C0B',
  border: '#232A26',
  surface: '#121513',
  ok: '#4ADE80',
  warn: '#F59E0B',
  err: '#EF4444',
  steam: '#93C5FD',
  flame: '#FCA5A5',
  amber: '#FCD34D',
  text: '#F8FAFC',
};

function metricColorTemp(t, max = 600) {
  if (t > max * 0.95) return C.err;
  if (t > max * 0.85) return C.warn;
  return C.ok;
}

// =========================
// SVG ANIMADO (estilo gráfico)
// =========================

export function ZapecadoMimic({ data, animated = true }) {
  const t = data?.temperatura ?? 0;
  const alim = data?.estado_alimentacion;
  const flameOpacity = alim ? 0.9 : 0.15;
  const color = metricColorTemp(t);
  return (
    <svg viewBox="0 0 480 240" className="w-full" data-testid="mimic-zap">
      <defs>
        <linearGradient id="hornoGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2a1410" />
          <stop offset="100%" stopColor="#1a0d0a" />
        </linearGradient>
        <radialGradient id="flame" cx="50%" cy="80%">
          <stop offset="0%" stopColor="#FCD34D" stopOpacity="1" />
          <stop offset="60%" stopColor="#FCA5A5" stopOpacity="0.7" />
          <stop offset="100%" stopColor="#7f1d1d" stopOpacity="0" />
        </radialGradient>
      </defs>
      {/* Tolva de chips */}
      <polygon points="50,20 130,20 100,80 80,80" fill={C.surface} stroke={C.border} />
      <text x="90" y="50" fill={C.text} fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle">CHIPS</text>
      {/* Cinta */}
      <rect x="80" y="80" width="80" height="6" fill={C.border} />
      {animated && alim && (
        <g>
          <circle r="2" fill={C.amber}>
            <animate attributeName="cx" from="80" to="160" dur="2s" repeatCount="indefinite" />
            <animate attributeName="cy" from="83" to="83" dur="2s" repeatCount="indefinite" />
          </circle>
          <circle r="2" fill={C.amber}>
            <animate attributeName="cx" from="80" to="160" dur="2s" begin="0.6s" repeatCount="indefinite" />
            <animate attributeName="cy" from="83" to="83" dur="2s" begin="0.6s" repeatCount="indefinite" />
          </circle>
        </g>
      )}
      {/* Horno (tambor) */}
      <ellipse cx="280" cy="140" rx="120" ry="55" fill="url(#hornoGrad)" stroke={C.border} strokeWidth="2" />
      {/* Llama */}
      <ellipse cx="280" cy="180" rx="100" ry="40" fill="url(#flame)" opacity={flameOpacity}>
        {animated && alim && <animate attributeName="ry" values="38;44;38" dur="1.8s" repeatCount="indefinite" />}
      </ellipse>
      {/* Tambor rotando */}
      <g transform="translate(280 140)">
        {animated && alim && (
          <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="6s" repeatCount="indefinite" />
        )}
        <circle r="42" fill="none" stroke={color} strokeWidth="2" opacity="0.8" />
        <line x1="-42" y1="0" x2="42" y2="0" stroke={color} strokeWidth="1" opacity="0.6" />
        <line x1="0" y1="-42" x2="0" y2="42" stroke={color} strokeWidth="1" opacity="0.6" />
      </g>
      {/* Salida */}
      <rect x="400" y="135" width="60" height="10" fill={C.border} />
      <polygon points="400,130 400,150 460,140" fill={C.border} />
      {/* Lecturas */}
      <text x="280" y="35" fill={color} fontSize="32" fontFamily="JetBrains Mono" fontWeight="300" textAnchor="middle">
        {t.toFixed(1)}°
      </text>
      <text x="280" y="55" fill={C.text} fontSize="11" fontFamily="JetBrains Mono" textAnchor="middle" opacity="0.6">TEMP HORNO</text>
      <text x="430" y="180" fill={C.text} fontSize="9" fontFamily="JetBrains Mono" textAnchor="middle" opacity="0.6">SALIDA</text>
      <text x="430" y="195" fill={alim ? C.ok : C.err} fontSize="11" fontFamily="JetBrains Mono" textAnchor="middle">
        {alim ? 'FEED ON' : 'FEED OFF'}
      </text>
    </svg>
  );
}

export function SecadoMimic({ data, animated = true }) {
  const t = data?.temperatura ?? 0;
  const h = data?.humedad ?? 0;
  const vAire = data?.velocidad_aire ?? 0;
  const active = data?.estado;
  const dur = active ? Math.max(0.5, 3 - vAire * 0.2) : 999;
  return (
    <svg viewBox="0 0 480 240" className="w-full" data-testid="mimic-sec">
      <defs>
        <linearGradient id="dryerGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={C.surface} />
          <stop offset="100%" stopColor="#1A1E1C" />
        </linearGradient>
      </defs>
      {/* Cuerpo del secador (horizontal) */}
      <rect x="60" y="80" width="360" height="80" fill="url(#dryerGrad)" stroke={C.border} strokeWidth="2" />
      <text x="240" y="105" fill={C.text} fontSize="9" fontFamily="JetBrains Mono" textAnchor="middle" opacity="0.4">SECADOR DE LECHO</text>
      {/* Ventilador izquierdo */}
      <g transform="translate(40 120)">
        <circle r="20" fill={C.surface} stroke={C.border} strokeWidth="1.5" />
        {animated && active && <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur={`${dur}s`} repeatCount="indefinite" additive="sum" />}
        <line x1="-15" y1="0" x2="15" y2="0" stroke={C.steam} strokeWidth="2.5" />
        <line x1="0" y1="-15" x2="0" y2="15" stroke={C.steam} strokeWidth="2.5" />
      </g>
      {/* Flechas de aire */}
      {animated && active && [110, 180, 250, 320].map((x, i) => (
        <g key={i}>
          <line x1={x} y1="120" x2={x + 30} y2="120" stroke={C.steam} strokeWidth="1.5" opacity="0.6">
            <animate attributeName="x1" from={x - 20} to={x + 30} dur="2s" begin={`${i * 0.2}s`} repeatCount="indefinite" />
            <animate attributeName="x2" from={x + 10} to={x + 60} dur="2s" begin={`${i * 0.2}s`} repeatCount="indefinite" />
            <animate attributeName="opacity" values="0;0.7;0" dur="2s" begin={`${i * 0.2}s`} repeatCount="indefinite" />
          </line>
        </g>
      ))}
      {/* Vapor saliendo arriba */}
      {animated && active && [120, 200, 280, 360].map((x, i) => (
        <circle key={i} cx={x} cy="75" r="3" fill={C.steam} opacity="0.4">
          <animate attributeName="cy" from="80" to="40" dur="3s" begin={`${i * 0.4}s`} repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.5;0" dur="3s" begin={`${i * 0.4}s`} repeatCount="indefinite" />
          <animate attributeName="r" from="2" to="5" dur="3s" begin={`${i * 0.4}s`} repeatCount="indefinite" />
        </circle>
      ))}
      {/* Lecturas */}
      <text x="240" y="200" fill={C.flame} fontSize="22" fontFamily="JetBrains Mono" fontWeight="300" textAnchor="middle">{t.toFixed(1)}°C</text>
      <text x="240" y="220" fill={C.steam} fontSize="22" fontFamily="JetBrains Mono" fontWeight="300" textAnchor="middle">{h.toFixed(1)}%</text>
      <text x="40" y="170" fill={C.text} fontSize="9" fontFamily="JetBrains Mono" textAnchor="middle" opacity="0.6">{vAire.toFixed(1)} m/s</text>
    </svg>
  );
}

export function CanchadoMimic({ data, animated = true }) {
  const rpm = data?.velocidad_molino ?? 0;
  const p = data?.tamano_particula ?? 0;
  const active = data?.estado;
  const dur = active ? Math.max(0.25, 60 / Math.max(rpm, 1)) : 999;
  return (
    <svg viewBox="0 0 480 240" className="w-full" data-testid="mimic-can">
      {/* Tolva de entrada */}
      <polygon points="60,30 140,30 110,90 90,90" fill={C.surface} stroke={C.border} />
      <text x="100" y="60" fill={C.text} fontSize="9" fontFamily="JetBrains Mono" textAnchor="middle">ENTRADA</text>
      {/* Molino */}
      <rect x="160" y="80" width="160" height="100" fill={C.surface} stroke={C.border} strokeWidth="2" />
      <g transform="translate(240 130)">
        {animated && active && <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur={`${dur}s`} repeatCount="indefinite" additive="sum" />}
        <circle r="35" fill="none" stroke="#D8B4FE" strokeWidth="2" />
        {[0, 45, 90, 135, 180, 225, 270, 315].map(a => (
          <line key={a} x1="0" y1="0" x2={28 * Math.cos(a * Math.PI / 180)} y2={28 * Math.sin(a * Math.PI / 180)} stroke="#D8B4FE" strokeWidth="2" opacity="0.7" />
        ))}
      </g>
      {/* Polvo cayendo */}
      {animated && active && [220, 240, 260].map((x, i) => (
        <circle key={i} cx={x} cy="180" r="1.5" fill="#D8B4FE" opacity="0.6">
          <animate attributeName="cy" from="180" to="220" dur="1s" begin={`${i * 0.2}s`} repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.8;0" dur="1s" begin={`${i * 0.2}s`} repeatCount="indefinite" />
        </circle>
      ))}
      {/* Salida */}
      <rect x="200" y="200" width="80" height="20" fill={C.border} />
      <text x="240" y="35" fill="#D8B4FE" fontSize="22" fontFamily="JetBrains Mono" fontWeight="300" textAnchor="middle">{rpm.toFixed(0)} rpm</text>
      <text x="240" y="55" fill={C.text} fontSize="9" fontFamily="JetBrains Mono" textAnchor="middle" opacity="0.6">VEL. MOLINO</text>
      <text x="380" y="130" fill={C.amber} fontSize="20" fontFamily="JetBrains Mono" fontWeight="300" textAnchor="middle">{p.toFixed(2)}</text>
      <text x="380" y="148" fill={C.text} fontSize="9" fontFamily="JetBrains Mono" textAnchor="middle" opacity="0.6">mm</text>
    </svg>
  );
}

export function CamaraMimic({ data, animated = true }) {
  const t = data?.temperatura ?? 0;
  const h = data?.humedad ?? 0;
  const co2 = data?.co2 ?? 0;
  const vent = data?.ventilador;
  const carga = data?.carga_kg ?? 0;
  const fill = Math.min(100, (carga / 1000) * 100);
  const co2Color = co2 > 5500 ? C.err : co2 > 4200 ? C.warn : C.ok;
  const vapor = data?.vapor_activo && data?.vapor_caudal_kgh > 0;
  return (
    <svg viewBox="0 0 480 260" className="w-full" data-testid={`mimic-cam-${data?.id ?? 0}`}>
      {/* Cámara - caja */}
      <rect x="60" y="30" width="380" height="180" fill={C.surface} stroke={C.border} strokeWidth="2" />
      <text x="250" y="22" fill={C.text} fontSize="11" fontFamily="JetBrains Mono" textAnchor="middle">{data?.nombre || 'Cámara'}</text>

      {/* Pila de yerba en el fondo */}
      <rect x="70" y={200 - fill * 1.4} width="360" height={fill * 1.4} fill="#3a2a1a" opacity="0.55" />
      {animated && carga > 0 && (
        <rect x="70" y={200 - fill * 1.4} width="360" height="2" fill={C.amber} opacity="0.7">
          <animate attributeName="opacity" values="0.3;0.9;0.3" dur="2.5s" repeatCount="indefinite" />
        </rect>
      )}

      {/* CO2 burbujas (de la pila hacia arriba) */}
      {animated && carga > 0 && [120, 220, 320].map((x, i) => (
        <circle key={i} cx={x} cy={195} r="2.5" fill={co2Color} opacity="0.55">
          <animate attributeName="cy" from="195" to={60} dur="4s" begin={`${i * 1.3}s`} repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.6;0" dur="4s" begin={`${i * 1.3}s`} repeatCount="indefinite" />
        </circle>
      ))}

      {/* Inyección de vapor desde arriba si está activa */}
      {animated && vapor && [180, 250, 320].map((x, i) => (
        <line key={`v${i}`} x1={x} y1={40} x2={x} y2={80} stroke={C.steam} strokeWidth="1.5" opacity="0.5">
          <animate attributeName="opacity" values="0.2;0.7;0.2" dur="1.5s" begin={`${i * 0.4}s`} repeatCount="indefinite" />
        </line>
      ))}

      {/* Ventilador */}
      <g transform="translate(410 60)">
        <circle r="18" fill={C.surface} stroke={C.border} />
        <g>
          {animated && vent && <animateTransform attributeName="transform" type="rotate" from="0" to="-360" dur="1.2s" repeatCount="indefinite" additive="sum" />}
          {[0, 90, 180, 270].map(a => (
            <path key={a} d="M0 0 Q 7 -9 12 0 Q 7 -3 0 0 Z" fill={vent ? C.steam : C.border} transform={`rotate(${a})`} />
          ))}
          <circle r="2.5" fill={vent ? C.steam : C.border} />
        </g>
      </g>

      {/* === LECTURAS GRANDES EN BANDA INFERIOR === */}
      <rect x="0" y="218" width="480" height="42" fill={C.bg} opacity="0.95" />
      {/* TEMP */}
      <text x="50" y="244" fill={C.flame} fontSize="22" fontFamily="JetBrains Mono" fontWeight="500" textAnchor="start">
        {`${Number(t).toFixed(1)}°C`}
      </text>
      <text x="50" y="256" fill={C.text} fontSize="8" fontFamily="JetBrains Mono" opacity="0.55" textAnchor="start">TEMP</text>
      {/* HR */}
      <text x="200" y="244" fill={C.steam} fontSize="22" fontFamily="JetBrains Mono" fontWeight="500" textAnchor="start">
        {`${Number(h).toFixed(1)}%`}
      </text>
      <text x="200" y="256" fill={C.text} fontSize="8" fontFamily="JetBrains Mono" opacity="0.55" textAnchor="start">HR</text>
      {/* CO2 */}
      <text x="330" y="244" fill={co2Color} fontSize="22" fontFamily="JetBrains Mono" fontWeight="500" textAnchor="start">
        {`${Number(co2).toFixed(0)}`}
      </text>
      <text x="330" y="256" fill={C.text} fontSize="8" fontFamily="JetBrains Mono" opacity="0.55" textAnchor="start">CO₂ ppm</text>

      {/* Carga (kg) arriba a la izquierda */}
      <text x="70" y="52" fill={C.amber} fontSize="14" fontFamily="JetBrains Mono" fontWeight="500">
        {`${Number(carga).toFixed(0)} kg`}
      </text>
      <text x="70" y="64" fill={C.text} fontSize="8" fontFamily="JetBrains Mono" opacity="0.5">CARGA</text>
    </svg>
  );
}

// =========================
// P&ID estilo industrial
// =========================

export function ZapecadoPid({ data }) {
  const t = data?.temperatura ?? 0;
  const c = metricColorTemp(t);
  return (
    <svg viewBox="0 0 480 220" className="w-full" data-testid="pid-zap">
      {/* Reactor / horno */}
      <rect x="180" y="60" width="160" height="80" fill="none" stroke={C.text} strokeWidth="1.5" />
      <text x="260" y="55" fill={C.text} fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle">R-101</text>
      {/* Línea de entrada */}
      <line x1="60" y1="100" x2="180" y2="100" stroke={C.text} strokeWidth="1.5" />
      <polygon points="60,100 70,95 70,105" fill={C.text} />
      <text x="120" y="92" fill={C.text} fontSize="9" fontFamily="JetBrains Mono">Chips</text>
      {/* Línea de salida */}
      <line x1="340" y1="100" x2="440" y2="100" stroke={C.text} strokeWidth="1.5" />
      <polygon points="430,95 440,100 430,105" fill={C.text} />
      <text x="380" y="92" fill={C.text} fontSize="9" fontFamily="JetBrains Mono">A Secado</text>
      {/* TIC - Temperature Indicator Controller */}
      <circle cx="260" cy="30" r="22" fill="none" stroke={c} strokeWidth="1.5" />
      <line x1="238" y1="30" x2="282" y2="30" stroke={c} strokeWidth="0.8" />
      <text x="260" y="27" fill={c} fontSize="9" fontFamily="JetBrains Mono" textAnchor="middle">TIC</text>
      <text x="260" y="40" fill={c} fontSize="9" fontFamily="JetBrains Mono" textAnchor="middle">101</text>
      <line x1="260" y1="52" x2="260" y2="60" stroke={c} strokeDasharray="2 2" />
      {/* Valor TI */}
      <text x="260" y="115" fill={c} fontSize="28" fontFamily="JetBrains Mono" fontWeight="300" textAnchor="middle">{t.toFixed(1)}</text>
      <text x="260" y="132" fill={C.text} fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle" opacity="0.6">°C</text>
      {/* Quemador */}
      <polygon points="240,140 280,140 270,180 250,180" fill="none" stroke={C.flame} strokeWidth="1.5" />
      <text x="260" y="195" fill={C.flame} fontSize="9" fontFamily="JetBrains Mono" textAnchor="middle">BURNER</text>
    </svg>
  );
}

export function SecadoPid({ data }) {
  const t = data?.temperatura ?? 0;
  const h = data?.humedad ?? 0;
  return (
    <svg viewBox="0 0 480 220" className="w-full" data-testid="pid-sec">
      {/* Dryer */}
      <rect x="100" y="80" width="280" height="60" fill="none" stroke={C.text} strokeWidth="1.5" />
      <text x="240" y="75" fill={C.text} fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle">DR-201</text>
      {/* Fan */}
      <circle cx="60" cy="110" r="20" fill="none" stroke={C.text} strokeWidth="1.5" />
      <line x1="60" y1="90" x2="60" y2="130" stroke={C.text} strokeWidth="1.2" />
      <line x1="40" y1="110" x2="80" y2="110" stroke={C.text} strokeWidth="1.2" />
      <text x="60" y="148" fill={C.text} fontSize="9" fontFamily="JetBrains Mono" textAnchor="middle">F-201</text>
      {/* Inlet/outlet */}
      <line x1="80" y1="110" x2="100" y2="110" stroke={C.text} strokeWidth="1.5" />
      <line x1="380" y1="110" x2="440" y2="110" stroke={C.text} strokeWidth="1.5" />
      <polygon points="430,105 440,110 430,115" fill={C.text} />
      <text x="410" y="100" fill={C.text} fontSize="9" fontFamily="JetBrains Mono">A Canchado</text>
      {/* TI */}
      <circle cx="180" cy="40" r="20" fill="none" stroke={C.flame} strokeWidth="1.5" />
      <text x="180" y="44" fill={C.flame} fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle">TI-201</text>
      <line x1="180" y1="60" x2="180" y2="80" stroke={C.flame} strokeDasharray="2 2" />
      {/* MI (humedad) */}
      <circle cx="300" cy="40" r="20" fill="none" stroke={C.steam} strokeWidth="1.5" />
      <text x="300" y="44" fill={C.steam} fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle">MI-201</text>
      <line x1="300" y1="60" x2="300" y2="80" stroke={C.steam} strokeDasharray="2 2" />
      {/* values */}
      <text x="180" y="170" fill={C.flame} fontSize="22" fontFamily="JetBrains Mono" textAnchor="middle">{t.toFixed(1)}°C</text>
      <text x="300" y="170" fill={C.steam} fontSize="22" fontFamily="JetBrains Mono" textAnchor="middle">{h.toFixed(1)}%</text>
    </svg>
  );
}

export function CanchadoPid({ data }) {
  const rpm = data?.velocidad_molino ?? 0;
  const p = data?.tamano_particula ?? 0;
  return (
    <svg viewBox="0 0 480 220" className="w-full" data-testid="pid-can">
      <rect x="160" y="80" width="160" height="80" fill="none" stroke={C.text} strokeWidth="1.5" />
      <text x="240" y="75" fill={C.text} fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle">M-301</text>
      <circle cx="240" cy="120" r="22" fill="none" stroke="#D8B4FE" strokeWidth="1.5" />
      <text x="240" y="124" fill="#D8B4FE" fontSize="9" fontFamily="JetBrains Mono" textAnchor="middle">MILL</text>
      {/* speed indicator */}
      <circle cx="240" cy="40" r="20" fill="none" stroke="#D8B4FE" strokeWidth="1.5" />
      <text x="240" y="44" fill="#D8B4FE" fontSize="9" fontFamily="JetBrains Mono" textAnchor="middle">SIC-301</text>
      <line x1="240" y1="60" x2="240" y2="80" stroke="#D8B4FE" strokeDasharray="2 2" />
      {/* outlet */}
      <line x1="320" y1="120" x2="440" y2="120" stroke={C.text} strokeWidth="1.5" />
      <polygon points="430,115 440,120 430,125" fill={C.text} />
      <text x="100" y="190" fill="#D8B4FE" fontSize="18" fontFamily="JetBrains Mono">{rpm.toFixed(0)} rpm</text>
      <text x="280" y="190" fill={C.amber} fontSize="18" fontFamily="JetBrains Mono">{p.toFixed(2)} mm</text>
    </svg>
  );
}

export function CamaraPid({ data }) {
  const t = data?.temperatura ?? 0;
  const h = data?.humedad ?? 0;
  const co2 = data?.co2 ?? 0;
  return (
    <svg viewBox="0 0 480 260" className="w-full" data-testid={`pid-cam-${data?.id ?? 0}`}>
      <rect x="60" y="30" width="380" height="160" fill="none" stroke={C.text} strokeWidth="1.5" />
      <text x="250" y="22" fill={C.text} fontSize="11" fontFamily="JetBrains Mono" textAnchor="middle">{data?.nombre || 'Cámara'}</text>

      {/* Bubbles tipo P&ID */}
      <circle cx="130" cy="100" r="22" fill="none" stroke={C.flame} strokeWidth="1.5" />
      <text x="130" y="98" fill={C.flame} fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle">TI</text>
      <text x="130" y="113" fill={C.flame} fontSize="8" fontFamily="JetBrains Mono" textAnchor="middle">PT100</text>

      <circle cx="250" cy="100" r="22" fill="none" stroke={C.steam} strokeWidth="1.5" />
      <text x="250" y="98" fill={C.steam} fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle">MI</text>
      <text x="250" y="113" fill={C.steam} fontSize="8" fontFamily="JetBrains Mono" textAnchor="middle">CAP</text>

      <circle cx="370" cy="100" r="22" fill="none" stroke={C.ok} strokeWidth="1.5" />
      <text x="370" y="98" fill={C.ok} fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle">QI</text>
      <text x="370" y="113" fill={C.ok} fontSize="8" fontFamily="JetBrains Mono" textAnchor="middle">NDIR</text>

      {/* Banda inferior con valores grandes (igual que SVG) */}
      <rect x="0" y="200" width="480" height="60" fill={C.bg} opacity="0.95" />
      <text x="130" y="232" fill={C.flame} fontSize="22" fontFamily="JetBrains Mono" fontWeight="500" textAnchor="middle">
        {`${Number(t).toFixed(1)}°C`}
      </text>
      <text x="130" y="246" fill={C.text} fontSize="9" fontFamily="JetBrains Mono" opacity="0.55" textAnchor="middle">T en pared</text>

      <text x="250" y="232" fill={C.steam} fontSize="22" fontFamily="JetBrains Mono" fontWeight="500" textAnchor="middle">
        {`${Number(h).toFixed(1)}%`}
      </text>
      <text x="250" y="246" fill={C.text} fontSize="9" fontFamily="JetBrains Mono" opacity="0.55" textAnchor="middle">Humedad rel.</text>

      <text x="370" y="232" fill={co2 > 4500 ? C.err : C.ok} fontSize="22" fontFamily="JetBrains Mono" fontWeight="500" textAnchor="middle">
        {`${Number(co2).toFixed(0)}`}
      </text>
      <text x="370" y="246" fill={C.text} fontSize="9" fontFamily="JetBrains Mono" opacity="0.55" textAnchor="middle">CO₂ ppm</text>
    </svg>
  );
}

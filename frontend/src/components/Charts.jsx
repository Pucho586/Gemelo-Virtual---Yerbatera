import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  AreaChart,
  Area,
} from 'recharts';

const COLORS = {
  temp: '#FCA5A5',
  hum: '#93C5FD',
  co2: '#86EFAC',
  rpm: '#D8B4FE',
  ambient: '#FCD34D',
};

const axisProps = {
  tick: { fill: '#6B7280', fontSize: 11, fontFamily: 'JetBrains Mono' },
  axisLine: false,
  tickLine: false,
};

const tooltipStyle = {
  backgroundColor: '#0A0C0B',
  border: '1px solid #232A26',
  borderRadius: 0,
  fontFamily: 'JetBrains Mono',
  fontSize: 12,
  color: '#F8FAFC',
};

function shortTs(ts) {
  try {
    const d = new Date(ts);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
  } catch (e) { return ''; }
}

export function flatten(series) {
  return series.map(s => ({
    t: shortTs(s.ts),
    ambient_t: s.ambient?.temp,
    ambient_h: s.ambient?.humidity,
    zap_t: s.zapecado?.temperatura,
    sec_t: s.secado?.temperatura,
    sec_h: s.secado?.humedad,
    can_p: s.canchado?.tamano_particula,
    can_rpm: s.canchado?.velocidad_molino,
    c1_t: s.camaras?.[0]?.temperatura,
    c1_h: s.camaras?.[0]?.humedad,
    c1_co2: s.camaras?.[0]?.co2,
    c2_t: s.camaras?.[1]?.temperatura,
    c2_h: s.camaras?.[1]?.humedad,
    c2_co2: s.camaras?.[1]?.co2,
    c3_t: s.camaras?.[2]?.temperatura,
    c3_h: s.camaras?.[2]?.humedad,
    c3_co2: s.camaras?.[2]?.co2,
    c4_t: s.camaras?.[3]?.temperatura,
    c4_h: s.camaras?.[3]?.humedad,
    c4_co2: s.camaras?.[3]?.co2,
  }));
}

export function ZapecadoChart({ data, height = 220 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 14, left: -10, bottom: 0 }}>
        <CartesianGrid stroke="#232A26" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="t" {...axisProps} minTickGap={32} />
        <YAxis domain={[0, 700]} {...axisProps} unit="°" />
        <Tooltip contentStyle={tooltipStyle} />
        <ReferenceLine y={600} stroke={COLORS.temp} strokeDasharray="4 4" label={{ value: 'Techo 600°C', position: 'right', fill: COLORS.temp, fontSize: 10, fontFamily: 'JetBrains Mono' }} />
        <ReferenceLine y={450} stroke="#4ADE80" strokeDasharray="2 6" label={{ value: 'Setpoint', position: 'left', fill: '#4ADE80', fontSize: 10, fontFamily: 'JetBrains Mono' }} />
        <Line type="monotone" dataKey="zap_t" stroke={COLORS.temp} strokeWidth={2} dot={false} name="Zapecado" />
        <Line type="monotone" dataKey="ambient_t" stroke={COLORS.ambient} strokeWidth={1.5} dot={false} strokeDasharray="4 3" name="Ambiente" />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function SecadoChart({ data, height = 220 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 14, left: -10, bottom: 0 }}>
        <CartesianGrid stroke="#232A26" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="t" {...axisProps} minTickGap={32} />
        <YAxis yAxisId="t" domain={[0, 130]} {...axisProps} unit="°" />
        <YAxis yAxisId="h" orientation="right" domain={[0, 100]} {...axisProps} unit="%" />
        <Tooltip contentStyle={tooltipStyle} />
        <Line yAxisId="t" type="monotone" dataKey="sec_t" stroke={COLORS.temp} strokeWidth={2} dot={false} name="Temp" />
        <Line yAxisId="h" type="monotone" dataKey="sec_h" stroke={COLORS.hum} strokeWidth={2} dot={false} name="Humedad" />
        <Line yAxisId="t" type="monotone" dataKey="ambient_t" stroke={COLORS.ambient} strokeWidth={1} dot={false} strokeDasharray="3 3" name="Ambiente" />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function CanchadoChart({ data, height = 220 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 14, left: -10, bottom: 0 }}>
        <defs>
          <linearGradient id="canGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={COLORS.rpm} stopOpacity={0.4} />
            <stop offset="100%" stopColor={COLORS.rpm} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#232A26" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="t" {...axisProps} minTickGap={32} />
        <YAxis domain={[0, 15]} {...axisProps} unit="mm" />
        <Tooltip contentStyle={tooltipStyle} />
        <Area type="monotone" dataKey="can_p" stroke={COLORS.rpm} strokeWidth={2} fill="url(#canGrad)" name="Tamaño partícula" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function CamarasChart({ data, metric = 'temp', height = 220 }) {
  // metric: 'temp' | 'hum' | 'co2'
  const keyMap = {
    temp: ['c1_t', 'c2_t', 'c3_t', 'c4_t'],
    hum: ['c1_h', 'c2_h', 'c3_h', 'c4_h'],
    co2: ['c1_co2', 'c2_co2', 'c3_co2', 'c4_co2'],
  };
  const colors = ['#FCA5A5', '#93C5FD', '#86EFAC', '#D8B4FE'];
  const unit = metric === 'temp' ? '°' : metric === 'hum' ? '%' : 'ppm';
  const domain = metric === 'co2' ? [0, 8000] : metric === 'temp' ? [0, 60] : [0, 100];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 14, left: -10, bottom: 0 }}>
        <CartesianGrid stroke="#232A26" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="t" {...axisProps} minTickGap={32} />
        <YAxis domain={domain} {...axisProps} unit={unit} />
        <Tooltip contentStyle={tooltipStyle} />
        {keyMap[metric].map((k, i) => (
          <Line key={k} type="monotone" dataKey={k} stroke={colors[i]} strokeWidth={2} dot={false} name={`Cámara ${i + 1}`} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function MiniSparkline({ data, dataKey, color = '#4ADE80', height = 36 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

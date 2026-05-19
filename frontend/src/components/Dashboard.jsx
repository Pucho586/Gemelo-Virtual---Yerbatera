import React from 'react';
import { Card, CardHeader, Metric, StatusBadge } from './UI';
import { flatten, MiniSparkline, ZapecadoChart, SecadoChart, CamarasChart } from './Charts';
import { Fire, Drop, Cube, Cloud, ThermometerSimple, MapPin } from '@phosphor-icons/react';

export default function Dashboard({ state, series, status }) {
  if (!state) return <div className="p-10 text-slate-500 font-mono">Conectando con el gemelo...</div>;
  const data = flatten(series);
  const z = state.zapecado;
  const s = state.secado;
  const c = state.canchado;
  const a = state.ambient;
  const cams = state.camaras || [];

  const zapColor = z.temperatura > 580 ? 'var(--red)' : z.temperatura > 540 ? 'var(--orange)' : 'var(--temp)';

  return (
    <div className="space-y-px">
      {/* Top strip: ambient + system status summary */}
      <Card className="p-5" testid="dashboard-ambient">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3 justify-between">
          <div className="flex items-center gap-2 text-slate-300">
            <MapPin size={16} className="text-amber-300" />
            <span className="font-display text-sm">{a.city || 'Sin ubicación'}</span>
            <span className="font-mono text-[10px] text-slate-500 ml-2">{a.latitude?.toFixed(2)}, {a.longitude?.toFixed(2)}</span>
          </div>
          <div className="flex items-center gap-6">
            <Metric label="T ambiente" value={a.temp?.toFixed(1) ?? '–'} unit="°C" color="var(--amber)" testid="dash-ambient-t" />
            <Metric label="HR ambiente" value={a.humidity?.toFixed(0) ?? '–'} unit="%" color="var(--hum)" testid="dash-ambient-h" />
            {a.wind_speed != null && <Metric label="Viento" value={a.wind_speed?.toFixed(1)} unit="km/h" color="var(--text-2)" testid="dash-ambient-w" />}
          </div>
        </div>
      </Card>

      {/* KPI row: 4 etapas */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-px hair-grid">
        <Card className="p-5" testid="kpi-zapecado">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2"><Fire size={16} className="text-red-300"/><span className="text-xs font-mono uppercase tracking-wider text-slate-400">Zapecado</span></div>
            <StatusBadge state={z.estado_alimentacion ? 'online' : 'warning'} label={z.estado_alimentacion ? 'feeding' : 'idle'} testid="kpi-zap-badge" />
          </div>
          <Metric label="Temperatura" value={z.temperatura.toFixed(1)} unit="°C" color={zapColor} big testid="kpi-zap-t" />
          <div className="mt-2"><MiniSparkline data={data} dataKey="zap_t" color="#FCA5A5" /></div>
        </Card>

        <Card className="p-5" testid="kpi-secado">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2"><Drop size={16} className="text-blue-300"/><span className="text-xs font-mono uppercase tracking-wider text-slate-400">Secado</span></div>
            <StatusBadge state={s.estado ? 'online' : 'offline'} label={s.estado ? 'on' : 'off'} testid="kpi-sec-badge" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Metric label="Temp" value={s.temperatura.toFixed(0)} unit="°C" color="var(--temp)" testid="kpi-sec-t" />
            <Metric label="HR" value={s.humedad.toFixed(1)} unit="%" color="var(--hum)" testid="kpi-sec-h" />
          </div>
          <div className="mt-2"><MiniSparkline data={data} dataKey="sec_h" color="#93C5FD" /></div>
        </Card>

        <Card className="p-5" testid="kpi-canchado">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2"><Cube size={16} className="text-purple-200"/><span className="text-xs font-mono uppercase tracking-wider text-slate-400">Canchado</span></div>
            <StatusBadge state={c.estado ? 'online' : 'offline'} label={c.estado ? 'on' : 'off'} testid="kpi-can-badge" />
          </div>
          <Metric label="Partícula" value={c.tamano_particula.toFixed(2)} unit="mm" color="var(--rpm, #D8B4FE)" big testid="kpi-can-p" />
          <div className="mt-2"><MiniSparkline data={data} dataKey="can_p" color="#D8B4FE" /></div>
        </Card>

        <Card className="p-5" testid="kpi-camaras">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2"><Cloud size={16} className="text-green-300"/><span className="text-xs font-mono uppercase tracking-wider text-slate-400">Cámaras</span></div>
            <span className="font-mono text-[10px] text-slate-500">{cams.length} unidades</span>
          </div>
          <div className="space-y-1.5">
            {cams.map((cm, i) => (
              <div key={i} className="flex items-center justify-between text-xs font-mono" data-testid={`kpi-cam-${i}`}>
                <span className="text-slate-400 truncate">{cm.nombre}</span>
                <span className="text-slate-200">{cm.temperatura.toFixed(1)}°<span className="text-slate-500"> / </span>{cm.humedad.toFixed(0)}%<span className="text-slate-500"> / </span><span className={cm.co2 > 5000 ? 'text-red-400' : cm.co2 > 4000 ? 'text-amber-400' : 'text-green-400'}>{cm.co2.toFixed(0)}</span></span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Charts overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-px hair-grid">
        <Card className="p-0" testid="overview-zap">
          <CardHeader title="Zapecado" subtitle="Temperatura del horno vs. ambiente" />
          <div className="p-3"><ZapecadoChart data={data} height={180} /></div>
        </Card>
        <Card className="p-0" testid="overview-sec">
          <CardHeader title="Secado" subtitle="Temperatura y humedad" />
          <div className="p-3"><SecadoChart data={data} height={180} /></div>
        </Card>
        <Card className="lg:col-span-2 p-0" testid="overview-cam">
          <CardHeader title="Cámaras · Temperatura" subtitle="Las 4 cámaras superpuestas" />
          <div className="p-3"><CamarasChart data={data} metric="temp" height={180} /></div>
        </Card>
      </div>
    </div>
  );
}

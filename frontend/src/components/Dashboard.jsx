import React from 'react';
import { Card, CardHeader } from './UI';
import { flatten, MiniSparkline, ZapecadoChart, SecadoChart, CamarasChart } from './Charts';
import { Gauge, BarGauge } from './Gauges';
import { zoneFor } from './Gauges';
import { TH } from '../lib/thresholds';
import { Fire, Drop, Cube, Cloud, MapPin, ThermometerSimple, Wind, CheckCircle, Warning, XCircle } from '@phosphor-icons/react';

// Salud global de la planta a partir de las variables clave.
function plantHealth(state) {
  const checks = [];
  const push = (v, th) => { const z = zoneFor(v, th.zones, th.max); if (z) checks.push(z.color); };
  if (state.zapecado) push(state.zapecado.temperatura, TH.zapecado_temp);
  if (state.secado) { push(state.secado.temperatura, TH.secado_temp); push(state.secado.humedad, TH.secado_hum); }
  if (state.canchado) push(state.canchado.tamano_particula, TH.canchado_part);
  (state.camaras || []).forEach(c => push(c.co2, TH.camara_co2));
  const bad = checks.filter(c => c === 'var(--red)').length;
  const warn = checks.filter(c => c === 'var(--amber)').length;
  if (bad > 0) return { level: 'bad', text: `${bad} variable${bad > 1 ? 's' : ''} en estado crítico`, Icon: XCircle, cls: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30' };
  if (warn > 0) return { level: 'warn', text: `${warn} variable${warn > 1 ? 's' : ''} en alerta`, Icon: Warning, cls: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30' };
  return { level: 'ok', text: 'Todos los procesos en rango óptimo', Icon: CheckCircle, cls: 'text-green-400', bg: 'bg-green-500/10 border-green-500/30' };
}

export default function Dashboard({ state, series, status }) {
  if (!state) return <div className="p-10 text-slate-500 font-mono">Conectando con el gemelo...</div>;
  const data = flatten(series);
  const z = state.zapecado;
  const s = state.secado;
  const c = state.canchado;
  const a = state.ambient;
  const cams = state.camaras || [];
  const health = plantHealth(state);
  // Peor cámara por CO₂ (la que dispara la alarma)
  const worstCam = cams.reduce((w, cm) => (cm.co2 > (w?.co2 ?? -1) ? cm : w), null);

  return (
    <div className="space-y-4">
      {/* Banner de salud + ambiente */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className={`lg:col-span-2 flex items-center gap-4 px-5 py-4 border rounded-lg ${health.bg}`} data-testid="plant-health">
          <health.Icon size={32} weight="duotone" className={health.cls} />
          <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400">Estado de la planta</div>
            <div className={`text-lg font-medium ${health.cls}`}>{health.text}</div>
          </div>
        </div>
        <div className="flex items-center justify-around px-5 py-4 border rounded-lg" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }} data-testid="dashboard-ambient">
          <div className="flex items-center gap-2 text-slate-300">
            <MapPin size={15} className="text-amber-300" />
            <div className="leading-tight">
              <div className="text-xs font-medium text-slate-200">{(a.city || 'Sin ubicación').split(',')[0]}</div>
              <div className="font-mono text-[10px] text-slate-500">ambiente</div>
            </div>
          </div>
          <AmbientStat Icon={ThermometerSimple} value={a.temp?.toFixed(1) ?? '–'} unit="°C" color="var(--amber)" testid="dash-ambient-t" />
          <AmbientStat Icon={Drop} value={a.humidity?.toFixed(0) ?? '–'} unit="%" color="var(--hum)" testid="dash-ambient-h" />
          {a.wind_speed != null && <AmbientStat Icon={Wind} value={a.wind_speed?.toFixed(0)} unit="km/h" color="var(--text-2)" testid="dash-ambient-w" />}
        </div>
      </div>

      {/* Gauges de las 4 etapas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StageCard Icon={Fire} title="Zapecado" iconCls="text-red-300" active={z.estado_alimentacion} activeLabel={z.estado_alimentacion ? 'Alimentando' : 'En pausa'} testid="stage-zapecado">
          <Gauge value={z.temperatura} {...TH.zapecado_temp} testid="gauge-zap" />
          <MiniSparkline data={data} dataKey="zap_t" color="#FCA5A5" />
        </StageCard>

        <StageCard Icon={Drop} title="Secado" iconCls="text-blue-300" active={s.estado} activeLabel={s.estado ? 'Encendido' : 'Apagado'} testid="stage-secado">
          <Gauge value={s.humedad} {...TH.secado_hum} testid="gauge-sec" />
          <div className="mt-1"><BarGauge value={s.temperatura} {...TH.secado_temp} testid="bar-sec-t" /></div>
        </StageCard>

        <StageCard Icon={Cube} title="Canchado" iconCls="text-purple-200" active={c.estado} activeLabel={c.estado ? 'Moliendo' : 'Detenido'} testid="stage-canchado">
          <Gauge value={c.tamano_particula} {...TH.canchado_part} testid="gauge-can" />
          <MiniSparkline data={data} dataKey="can_p" color="#D8B4FE" />
        </StageCard>

        <StageCard Icon={Cloud} title="Cámaras" iconCls="text-green-300" active={cams.length > 0} activeLabel={`${cams.length} unidades`} testid="stage-camaras">
          <Gauge value={worstCam?.co2} {...TH.camara_co2} label="CO₂ (peor cámara)" testid="gauge-cam" />
          <div className="space-y-1 mt-1">
            {cams.slice(0, 4).map((cm, i) => (
              <BarGauge key={i} value={cm.co2} {...TH.camara_co2} label={cm.nombre} testid={`bar-cam-${i}`} />
            ))}
          </div>
        </StageCard>
      </div>

      {/* Gráficos con banda de operación */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="p-0" testid="overview-zap">
          <CardHeader title="Zapecado" subtitle="Temperatura del horno · banda verde = rango seguro" />
          <div className="p-3"><ZapecadoChart data={data} height={200} /></div>
        </Card>
        <Card className="p-0" testid="overview-sec">
          <CardHeader title="Secado" subtitle="Temperatura y humedad de la yerba" />
          <div className="p-3"><SecadoChart data={data} height={200} /></div>
        </Card>
        <Card className="lg:col-span-2 p-0" testid="overview-cam">
          <CardHeader title="Cámaras · CO₂" subtitle="Las 4 cámaras · umbral de alerta 4200 ppm" />
          <div className="p-3"><CamarasChart data={data} metric="co2" height={200} /></div>
        </Card>
      </div>
    </div>
  );
}

function StageCard({ Icon, title, iconCls, active, activeLabel, children, testid }) {
  return (
    <Card className="p-5 flex flex-col items-center" testid={testid}>
      <div className="flex items-center justify-between w-full mb-2">
        <div className="flex items-center gap-2"><Icon size={16} className={iconCls} weight="duotone" /><span className="text-sm font-medium text-slate-200">{title}</span></div>
        <span className={`inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider ${active ? 'text-green-400' : 'text-slate-500'}`}>
          <span className={active ? 'live-dot text-green-400' : 'text-slate-600'}>●</span>{activeLabel}
        </span>
      </div>
      <div className="w-full flex flex-col items-center gap-2">{children}</div>
    </Card>
  );
}

function AmbientStat({ Icon, value, unit, color, testid }) {
  return (
    <div className="flex flex-col items-center" data-testid={testid}>
      <Icon size={16} style={{ color }} weight="duotone" />
      <div className="font-mono text-lg font-light" style={{ color }}>{value}<span className="text-xs text-slate-500 ml-0.5">{unit}</span></div>
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Metric, Toggle, NumberInput, SectionTitle } from './UI';
import { CamarasChart, flatten } from './Charts';
import { CamaraMimic, CamaraPid } from './Mimics';
import { api } from '../lib/api';
import { Cloud, Drop, Thermometer, Fan, Package } from '@phosphor-icons/react';

function ChamberCard({ cam, idx, mimicStyle }) {
  const [carga, setCarga] = useState(cam.carga_kg);
  const [vent, setVent] = useState(cam.ventilador);
  const [tObj, setTObj] = useState(cam.temperatura_obj);
  const [hObj, setHObj] = useState(cam.humedad_obj);
  const [co2Obj, setCo2Obj] = useState(cam.co2_obj);

  useEffect(() => {
    setCarga(cam.carga_kg);
    setVent(cam.ventilador);
    setTObj(cam.temperatura_obj);
    setHObj(cam.humedad_obj);
    setCo2Obj(cam.co2_obj);
  }, [cam.carga_kg, cam.ventilador, cam.temperatura_obj, cam.humedad_obj, cam.co2_obj]);

  const apply = (patch) => api.patchCamara(idx, patch).catch(e => console.warn(e));

  const co2Color = cam.co2 > 5500 ? 'var(--red)' : cam.co2 > 4200 ? 'var(--orange)' : 'var(--co2)';
  const tempDev = Math.abs(cam.temperatura - cam.temperatura_obj);
  const tempColor = tempDev > 4 ? 'var(--orange)' : 'var(--temp)';

  return (
    <Card className="p-5" testid={`camara-card-${idx}`}>
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-display text-base font-medium text-slate-100">{cam.nombre}</h4>
        <span className="font-mono text-[10px] text-slate-500">ID #{idx + 1}</span>
      </div>
      <div className="mb-4 border" style={{ borderColor: 'var(--border)' }}>
        {mimicStyle === 'pid' ? <CamaraPid data={cam} /> : <CamaraMimic data={cam} />}
      </div>
      <div className="grid grid-cols-3 gap-4 mb-4">
        <Metric label="Temp" value={cam.temperatura.toFixed(1)} unit="°C" color={tempColor} testid={`cam-${idx}-temp`} />
        <Metric label="HR" value={cam.humedad.toFixed(0)} unit="%" color="var(--hum)" testid={`cam-${idx}-hum`} />
        <Metric label="CO₂" value={cam.co2.toFixed(0)} unit="ppm" color={co2Color} testid={`cam-${idx}-co2`} />
      </div>
      <div className="grid grid-cols-2 gap-4 mb-4 text-xs">
        <div className="flex items-center gap-1.5 text-slate-400"><Package size={14}/> Carga: <span className="font-mono text-slate-200 ml-auto">{cam.carga_kg} kg</span></div>
        <div className="flex items-center gap-1.5 text-slate-400">Días: <span className="font-mono text-slate-200 ml-auto">{cam.tiempo_maduracion.toFixed(2)}</span></div>
      </div>

      <div className="grid grid-cols-2 gap-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
        <NumberInput testid={`cam-${idx}-carga`} label="Carga" unit="kg" value={carga} onChange={(v) => { setCarga(v); apply({ carga_kg: v || 0 }); }} min={0} max={5000} step={10} />
        <div className="flex items-end justify-between">
          <Toggle testid={`cam-${idx}-vent`} value={vent} onChange={(v) => { setVent(v); apply({ ventilador: v }); }} label={<span className="flex items-center gap-1"><Fan size={12}/> {vent ? 'On' : 'Off'}</span>} />
        </div>
        <NumberInput testid={`cam-${idx}-tobj`} label="Obj T" unit="°C" value={tObj} onChange={(v) => { setTObj(v); apply({ temperatura_obj: v }); }} min={20} max={50} step={0.5} />
        <NumberInput testid={`cam-${idx}-hobj`} label="Obj HR" unit="%" value={hObj} onChange={(v) => { setHObj(v); apply({ humedad_obj: v }); }} min={40} max={95} step={1} />
        <NumberInput testid={`cam-${idx}-co2obj`} label="Obj CO₂" unit="ppm" value={co2Obj} onChange={(v) => { setCo2Obj(v); apply({ co2_obj: v }); }} min={400} max={6000} step={50} className="col-span-2" />
      </div>
    </Card>
  );
}

export default function CamarasView({ state, series, mimicStyle = 'svg' }) {
  const camaras = state?.camaras || [];
  const data = flatten(series);
  const [metric, setMetric] = useState('temp'); // temp | hum | co2

  return (
    <div className="space-y-px">
      <Card className="p-0" testid="camaras-chart-card">
        <CardHeader
          title="Cámaras · Comparativa en tiempo real"
          subtitle="Cuando ventilador apaga, las cámaras intercambian calor con el ambiente (modelo realista)"
          action={
            <div className="flex items-center gap-1 border" style={{ borderColor: 'var(--border)' }}>
              {[
                ['temp', 'Temp', Thermometer],
                ['hum', 'HR', Drop],
                ['co2', 'CO₂', Cloud],
              ].map(([k, lbl, Icon]) => (
                <button key={k} data-testid={`camaras-metric-${k}`} onClick={() => setMetric(k)} className={`px-2.5 py-1 text-xs flex items-center gap-1 font-mono transition-colors ${metric === k ? 'bg-slate-50 text-slate-900' : 'text-slate-400 hover:bg-[#1A1E1C]'}`}>
                  <Icon size={12} /> {lbl}
                </button>
              ))}
            </div>
          }
        />
        <div className="p-2 sm:p-4">
          <CamarasChart data={data} metric={metric} />
        </div>
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-px hair-grid">
        {camaras.map((cam, i) => (
          <ChamberCard key={i} cam={cam} idx={i} mimicStyle={mimicStyle} />
        ))}
      </div>
    </div>
  );
}

import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Metric, Toggle, NumberInput, SectionTitle, Btn } from './UI';
import { CamarasChart, flatten } from './Charts';
import { CamaraMimic, CamaraPid } from './Mimics';
import { ChamberSensorsBlock } from './StageBlock';
import { api } from '../lib/api';
import { useAuth, isAdmin } from '../lib/auth';
import { Cloud, Drop, Thermometer, Fan, Package, Drop as Vapor, Plus, Minus } from '@phosphor-icons/react';

function ChamberCard({ cam, idx, mimicStyle }) {
  const [carga, setCarga] = useState(cam.carga_kg);
  const [vent, setVent] = useState(cam.ventilador);
  const [tObj, setTObj] = useState(cam.temperatura_obj);
  const [hObj, setHObj] = useState(cam.humedad_obj);
  const [co2Obj, setCo2Obj] = useState(cam.co2_obj);
  const [vaporOn, setVaporOn] = useState(cam.vapor_activo || false);
  const [vaporCaudal, setVaporCaudal] = useState(cam.vapor_caudal_kgh || 0);
  const [vaporT, setVaporT] = useState(cam.vapor_setpoint_temp || cam.temperatura_obj);
  const [vaporH, setVaporH] = useState(cam.vapor_setpoint_hum || cam.humedad_obj);

  useEffect(() => {
    setCarga(cam.carga_kg);
    setVent(cam.ventilador);
    setTObj(cam.temperatura_obj);
    setHObj(cam.humedad_obj);
    setCo2Obj(cam.co2_obj);
    setVaporOn(cam.vapor_activo || false);
    setVaporCaudal(cam.vapor_caudal_kgh || 0);
    setVaporT(cam.vapor_setpoint_temp || cam.temperatura_obj);
    setVaporH(cam.vapor_setpoint_hum || cam.humedad_obj);
  }, [cam.carga_kg, cam.ventilador, cam.temperatura_obj, cam.humedad_obj, cam.co2_obj,
      cam.vapor_activo, cam.vapor_caudal_kgh, cam.vapor_setpoint_temp, cam.vapor_setpoint_hum]);

  const apply = (patch) => api.patchCamara(idx, patch).catch(e => console.warn(e));

  const co2Color = cam.co2 > 5500 ? 'var(--red)' : cam.co2 > 4200 ? 'var(--orange)' : 'var(--co2)';
  const tempDev = Math.abs(cam.temperatura - cam.temperatura_obj);
  const tempColor = tempDev > 4 ? 'var(--orange)' : 'var(--temp)';

  return (
    <Card className="p-5" testid={`camara-card-${idx}`}>
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-display text-base font-medium text-slate-100">{cam.nombre}</h4>
        <span className="font-mono text-[10px] text-slate-500">ID #{idx + 1}{cam.vapor_activo && cam.vapor_caudal_kgh > 0 && <span className="ml-2 text-cyan-300">·VAPOR</span>}</span>
      </div>
      <div className="mb-4 border" style={{ borderColor: 'var(--border)' }}>
        {mimicStyle === 'pid' ? <CamaraPid data={cam} /> : <CamaraMimic data={cam} />}
      </div>
      <div className="grid grid-cols-4 gap-3 mb-4">
        <Metric label="Temp" value={cam.temperatura.toFixed(1)} unit="°C" color={tempColor} testid={`cam-${idx}-temp`} />
        <Metric label="HR" value={cam.humedad.toFixed(0)} unit="%" color="var(--hum)" testid={`cam-${idx}-hum`} />
        <Metric label="CO₂" value={cam.co2.toFixed(0)} unit="ppm" color={co2Color} testid={`cam-${idx}-co2`} />
        <Metric label="Vapor ac." value={(cam.vapor_kg_acum || 0).toFixed(1)} unit="kg" color="#67E8F9" testid={`cam-${idx}-vapor-acum`} />
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

      {/* Sensores derivados (PT100 doble + CO2 NDIR + vapor) */}
      <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
        <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Sensores de campo</span>
        <ChamberSensorsBlock cam={cam} />
      </div>

      {/* Inyección de vapor */}
      <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-300 flex items-center gap-1"><Vapor size={12}/> Inyección de vapor</span>
          <Toggle testid={`cam-${idx}-vapor`} value={vaporOn} onChange={(v) => { setVaporOn(v); apply({ vapor_activo: v }); }} label={vaporOn ? 'ON' : 'OFF'} />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <NumberInput testid={`cam-${idx}-vapor-caudal`} label="Caudal" unit="kg/h" value={vaporCaudal} onChange={(v) => { setVaporCaudal(v); apply({ vapor_caudal_kgh: v || 0 }); }} min={0} max={200} step={1} />
          <NumberInput testid={`cam-${idx}-vapor-tsp`} label="SP Temp" unit="°C" value={vaporT} onChange={(v) => { setVaporT(v); apply({ vapor_setpoint_temp: v }); }} min={20} max={60} step={0.5} />
          <NumberInput testid={`cam-${idx}-vapor-hsp`} label="SP HR" unit="%" value={vaporH} onChange={(v) => { setVaporH(v); apply({ vapor_setpoint_hum: v }); }} min={40} max={98} step={1} />
        </div>
      </div>
    </Card>
  );
}

export default function CamarasView({ state, series, mimicStyle = 'svg' }) {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const camaras = state?.camaras || [];
  const data = flatten(series);
  const [metric, setMetric] = useState('temp'); // temp | hum | co2
  const MAX = 12;

  const changeCount = async (delta) => {
    const target = Math.max(1, Math.min(MAX, camaras.length + delta));
    if (target === camaras.length) return;
    try { await api.setCamarasCount(target); }
    catch (e) { console.warn(e); }
  };

  return (
    <div className="space-y-px">
      <Card className="p-5" testid="camaras-explain">
        <SectionTitle kicker="?">¿Cómo funcionan las cámaras de maduración?</SectionTitle>
        <p className="text-sm text-slate-300 mt-2 leading-relaxed">
          Después del canchado, la yerba pasa al <span className="text-amber-300">estacionamiento</span>: se acopia en cámaras controladas durante
          semanas o meses para que pierda el sabor "verde" y desarrolle aroma. El gemelo te deja:
        </p>
        <ul className="text-xs text-slate-400 font-mono mt-3 space-y-1.5 pl-3">
          <li>• <span className="text-green-400">Cantidad de cámaras</span>: 1 a 12 (botones +/- arriba a la derecha). Cuando transferís yerba al
              estacionamiento, los kg se reparten en la cámara con menor carga (load balancing).</li>
          <li>• <span className="text-green-400">Ventilador</span> (modo natural): mueve el aire dentro de la cámara para acercarla a su setpoint de T y HR.</li>
          <li>• <span className="text-cyan-300">Inyección de vapor</span> (modo acelerado): toggle ON + caudal en kg/h. Fuerza la cámara hacia un
              setpoint propio mucho más rápido (60-180s vs 600s del modo natural). Útil para simular maduración acelerada con caldera + serpentín.</li>
          <li>• <span className="text-blue-300">Carga (kg)</span>: cantidad de yerba dentro. Se incrementa al transferir desde Canchado o manualmente.</li>
          <li>• <span className="text-violet-300">Días maduración</span>: tiempo acumulado con carga &gt; 0 (en días simulados).</li>
          <li>• <span className="text-amber-300">CO₂ (ppm)</span>: la yerba respira durante el añejado, sube el CO₂ si no se ventila.</li>
        </ul>
        <p className="text-[11px] font-mono text-slate-500 mt-3 leading-relaxed">
          Los sensores reales (PT100 doble, NDIR, caudalímetro de vapor) se muestran dentro de cada card de cámara.
        </p>
      </Card>

      <Card className="p-0" testid="camaras-chart-card">
        <CardHeader
          title="Cámaras · Comparativa en tiempo real"
          subtitle={`${camaras.length} cámara(s) activas · ventilador y vapor controlables por cámara`}
          action={
            <div className="flex items-center gap-3">
              {admin && (
                <div className="flex items-center gap-1 border px-1" style={{ borderColor: 'var(--border)' }} data-testid="camaras-count-ctl">
                  <button onClick={() => changeCount(-1)} disabled={camaras.length <= 1} data-testid="camaras-count-minus" className="px-2 py-1 text-slate-300 hover:text-amber-300 disabled:opacity-30"><Minus size={12}/></button>
                  <span className="font-mono text-xs text-slate-200 min-w-[2ch] text-center" data-testid="camaras-count-value">{camaras.length}</span>
                  <button onClick={() => changeCount(+1)} disabled={camaras.length >= MAX} data-testid="camaras-count-plus" className="px-2 py-1 text-slate-300 hover:text-amber-300 disabled:opacity-30"><Plus size={12}/></button>
                </div>
              )}
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

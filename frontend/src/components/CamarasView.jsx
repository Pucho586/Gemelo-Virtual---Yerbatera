import React from 'react';
import { Card, CardHeader, Metric, Toggle, NumberInput, SectionTitle } from './UI';
import { CamarasChart, flatten } from './Charts';
import { CamaraMimic, CamaraPid } from './Mimics';
import FaultPanel from './FaultPanel';
import PidPanel from './PidPanel';
import { useLocalSync } from '../lib/useLocalSync';
import { api } from '../lib/api';
import { useAuth, isAdmin } from '../lib/auth';
import { Cloud, Drop, Thermometer, Fan, Plus, Minus } from '@phosphor-icons/react';

function ChamberCard({ cam, idx, mimicStyle }) {
  const [carga, setCarga] = useLocalSync(cam.carga_kg);
  const [vent, setVent] = useLocalSync(cam.ventilador);
  const [tObj, setTObj] = useLocalSync(cam.temperatura_obj);
  const [hObj, setHObj] = useLocalSync(cam.humedad_obj);
  const [co2Obj, setCo2Obj] = useLocalSync(cam.co2_obj);
  const [tau, setTau] = useLocalSync(cam.tau ?? 600);
  const [vaporOn, setVaporOn] = useLocalSync(cam.vapor_activo || false);
  const [vaporCaudal, setVaporCaudal] = useLocalSync(cam.vapor_caudal_kgh || 0);
  const [vaporT, setVaporT] = useLocalSync(cam.vapor_setpoint_temp || cam.temperatura_obj);
  const [vaporH, setVaporH] = useLocalSync(cam.vapor_setpoint_hum || cam.humedad_obj);

  const apply = (patch) => api.patchCamara(idx, patch).catch(e => console.warn(e));

  const co2Color = cam.co2 > 5500 ? 'var(--red)' : cam.co2 > 4200 ? 'var(--orange)' : 'var(--co2)';
  const tempDev = Math.abs(cam.temperatura - cam.temperatura_obj);
  const tempColor = tempDev > 4 ? 'var(--orange)' : 'var(--temp)';
  const faults = cam.faults || {};

  return (
    <Card className="p-5" testid={`camara-card-${idx}`}>
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-display text-base font-medium text-slate-100">{cam.nombre}</h4>
        <span className="font-mono text-[10px] text-slate-500">ID #{idx + 1}{cam.vapor_activo && cam.vapor_caudal_kgh > 0 && <span className="ml-2 text-cyan-300">·VAPOR</span>}</span>
      </div>

      {/* === LAYOUT 2 COLUMNAS === */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* COLUMNA IZQUIERDA: Mímico + lecturas REAL vs SP */}
        <div className="space-y-3">
          <div className="border" style={{ borderColor: 'var(--border)' }}>
            {mimicStyle === 'pid' ? <CamaraPid data={cam} /> : <CamaraMimic data={cam} />}
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="border p-2" style={{ borderColor: 'var(--border)' }}>
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">T real</div>
              <div className="text-lg font-mono" style={{ color: tempColor }} data-testid={`cam-${idx}-temp`}>{cam.temperatura.toFixed(1)}°</div>
              <div className="text-[10px] font-mono text-amber-400">SP {cam.temperatura_obj.toFixed(0)}°</div>
            </div>
            <div className="border p-2" style={{ borderColor: 'var(--border)' }}>
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">HR real</div>
              <div className="text-lg font-mono" style={{ color: 'var(--hum)' }} data-testid={`cam-${idx}-hum`}>{cam.humedad.toFixed(0)}%</div>
              <div className="text-[10px] font-mono text-amber-400">SP {cam.humedad_obj.toFixed(0)}%</div>
            </div>
            <div className="border p-2" style={{ borderColor: 'var(--border)' }}>
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">CO₂</div>
              <div className="text-lg font-mono" style={{ color: co2Color }} data-testid={`cam-${idx}-co2`}>{cam.co2.toFixed(0)}</div>
              <div className="text-[10px] font-mono text-amber-400">SP {cam.co2_obj.toFixed(0)}</div>
            </div>
          </div>
          <div className="text-[11px] font-mono text-slate-500 grid grid-cols-3 gap-2">
            <div>Carga: <span className="text-slate-200">{cam.carga_kg} kg</span></div>
            <div>Días: <span className="text-slate-200">{cam.tiempo_maduracion.toFixed(2)}</span></div>
            <div>Vapor ac.: <span className="text-cyan-300">{(cam.vapor_kg_acum || 0).toFixed(1)} kg</span></div>
          </div>
        </div>

        {/* COLUMNA DERECHA: Controles (carga, SP, τ, ventilador, vapor) */}
        <div className="space-y-4">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-2">Carga y ventilación</div>
            <div className="grid grid-cols-2 gap-3">
              <NumberInput testid={`cam-${idx}-carga`} label="Carga" unit="kg" value={carga} onChange={(v) => { setCarga(v); apply({ carga_kg: v || 0 }); }} min={0} max={5000} step={10} />
              <div className="flex items-end justify-between">
                <Toggle testid={`cam-${idx}-vent`} value={vent} onChange={(v) => { setVent(v); apply({ ventilador: v }); }} label={<span className="flex items-center gap-1 text-xs"><Fan size={12}/> {vent ? 'ON' : 'OFF'}</span>} />
              </div>
            </div>
          </div>

          <div className="pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-2">Setpoints (objetivos)</div>
            <div className="grid grid-cols-2 gap-3">
              <NumberInput testid={`cam-${idx}-tobj`} label="SP T" unit="°C" value={tObj} onChange={(v) => { setTObj(v); apply({ temperatura_obj: v }); }} min={20} max={50} step={0.5} />
              <NumberInput testid={`cam-${idx}-hobj`} label="SP HR" unit="%" value={hObj} onChange={(v) => { setHObj(v); apply({ humedad_obj: v }); }} min={40} max={95} step={1} />
              <NumberInput testid={`cam-${idx}-co2obj`} label="SP CO₂" unit="ppm" value={co2Obj} onChange={(v) => { setCo2Obj(v); apply({ co2_obj: v }); }} min={400} max={6000} step={50} />
              <NumberInput testid={`cam-${idx}-tau`} label="τ cámara" unit="s" hint="↓ τ = más rápido" value={tau} onChange={(v) => { setTau(v); apply({ tau: v }); }} min={30} max={3600} step={30} />
            </div>
          </div>

          <div className="pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-300">💧 Inyección vapor / agua por techo</span>
              <Toggle testid={`cam-${idx}-vapor`} value={vaporOn} onChange={(v) => { setVaporOn(v); apply({ vapor_activo: v }); }} label={vaporOn ? 'ON' : 'OFF'} />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <NumberInput testid={`cam-${idx}-vapor-caudal`} label="Caudal" unit="kg/h" value={vaporCaudal} onChange={(v) => { setVaporCaudal(v); apply({ vapor_caudal_kgh: v || 0 }); }} min={0} max={200} step={1} />
              <NumberInput testid={`cam-${idx}-vapor-tsp`} label="SP T vap" unit="°C" value={vaporT} onChange={(v) => { setVaporT(v); apply({ vapor_setpoint_temp: v }); }} min={20} max={60} step={0.5} />
              <NumberInput testid={`cam-${idx}-vapor-hsp`} label="SP HR vap" unit="%" value={vaporH} onChange={(v) => { setVaporH(v); apply({ vapor_setpoint_hum: v }); }} min={40} max={98} step={1} />
            </div>
          </div>
        </div>
      </div>

      {/* === PID + FALLAS (todo el ancho) === */}
      <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-px hair-grid">
        <PidPanel
          title="PID Temperatura cámara · ajusta vapor"
          pid={cam.pid_t}
          manipulada="caudal vapor (kg/h)"
          onApply={(patch) => apply({ pid_t: patch })}
          testidBase={`cam-${idx}-pid-t`}
        />
        <FaultPanel
          title="Inyección de fallas"
          faults={faults}
          defs={[
            { key: 'falla_ventilador', label: 'Falla ventilador', hint: 'Sin circulación: HR no converge, CO₂ sube.' },
            { key: 'fuga_vapor', label: 'Fuga de vapor', hint: 'Se consume vapor sin aportar al ambiente interno.' },
            { key: 'puerta_abierta', label: 'Puerta / techo abierta', hint: 'Pérdida acelerada hacia ambiente exterior.' },
          ]}
          onApply={apply}
          testidBase={`cam-${idx}-fault`}
        />
      </div>
    </Card>
  );
}

export default function CamarasView({ state, series, mimicStyle = 'svg' }) {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const camaras = state?.camaras || [];
  const data = flatten(series);
  const [metric, setMetric] = React.useState('temp');
  const MAX = 12;

  const changeCount = async (delta) => {
    const target = Math.max(1, Math.min(MAX, camaras.length + delta));
    if (target === camaras.length) return;
    try { await api.setCamarasCount(target); } catch (e) { console.warn(e); }
  };

  return (
    <div className="space-y-px">
      <Card className="p-0" testid="camaras-chart-card">
        <CardHeader
          title="Cámaras · Comparativa en tiempo real"
          subtitle={`${camaras.length} cámara(s) · SP, τ y fallas configurables por cámara`}
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

      <div className="grid grid-cols-1 gap-px hair-grid">
        {camaras.map((cam, i) => (
          <ChamberCard key={i} cam={cam} idx={i} mimicStyle={mimicStyle} />
        ))}
      </div>

      <Card className="p-5" testid="camaras-explain">
        <SectionTitle kicker="?">¿Cómo funcionan las cámaras de maduración?</SectionTitle>
        <ul className="text-xs text-slate-400 font-mono mt-2 space-y-1.5 pl-3 leading-relaxed">
          <li>• <span className="text-green-400">Izquierda</span>: mímico + lecturas REAL vs SP (T, HR, CO₂). El valor real se acerca al SP <em>con el tiempo</em> según τ.</li>
          <li>• <span className="text-green-400">Derecha</span>: controles (carga, ventilador, SPs, τ, vapor).</li>
          <li>• <span className="text-amber-300">τ cámara</span>: bajalo (60 s) para ver cambios rápidos; subilo (1800 s) para realismo.</li>
          <li>• <span className="text-cyan-300">Inyección vapor/agua</span>: toggle ON + caudal → fuerza T/HR hacia SP propio muy rápido (caldera o ducha húmeda).</li>
          <li>• <span className="text-red-300">Fallas</span>: probá apagar el ventilador y mirá cómo el CO₂ sube y la HR no converge.</li>
        </ul>
        <p className="text-[11px] font-mono text-slate-500 mt-3 leading-relaxed">
          Todo (SPs, τ, fallas, vapor) expuesto a Modbus/OPC UA. Ver Manual técnico.
        </p>
      </Card>
    </div>
  );
}

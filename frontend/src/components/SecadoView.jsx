import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Metric, Toggle, Slider, NumberInput, SectionTitle } from './UI';
import { SecadoChart, flatten } from './Charts';
import { SecadoMimic, SecadoPid } from './Mimics';
import StageBlock from './StageBlock';
import FaultPanel from './FaultPanel';
import { api } from '../lib/api';
import { Drop } from '@phosphor-icons/react';

export default function SecadoView({ state, series, mimicStyle = 'svg' }) {
  const s = state?.secado;
  const ambient = state?.ambient;
  const faults = s?.faults || {};
  const [aire, setAire] = useState(s?.velocidad_aire ?? 2.5);
  const [estado, setEstado] = useState(s?.estado ?? true);
  const [tObj, setTObj] = useState(s?.temperatura_obj ?? 95);
  const [hObj, setHObj] = useState(s?.humedad_obj ?? 7);
  const [tau, setTau] = useState(s?.tau_t ?? 120);

  useEffect(() => {
    if (s) {
      setAire(s.velocidad_aire);
      setEstado(s.estado);
      setTObj(s.temperatura_obj ?? 95);
      setHObj(s.humedad_obj ?? 7);
      setTau(s.tau_t ?? 120);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s?.velocidad_aire, s?.estado, s?.temperatura_obj, s?.humedad_obj, s?.tau_t]);

  const apply = async (patch) => {
    try { await api.patchSecado(patch); } catch (e) { console.warn(e); }
  };

  const data = flatten(series);
  const t = s?.temperatura ?? 0;
  const hum = s?.humedad ?? 0;
  const humColor = hum < 7 ? 'var(--red)' : hum > 30 ? 'var(--orange)' : 'var(--green)';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-px hair-grid">
      <Card className="lg:col-span-2 p-0" testid="secado-mimic-card">
        <CardHeader title="Secado · Mímico" subtitle={mimicStyle === 'pid' ? 'P&ID estándar' : 'Vista animada del secador'} />
        <div className="p-4">{mimicStyle === 'pid' ? <SecadoPid data={s} /> : <SecadoMimic data={s} />}</div>
      </Card>

      <Card className="p-6" testid="secado-controls-card">
        <div className="flex items-center gap-2 mb-4">
          <Drop size={18} weight="duotone" className="text-blue-300" />
          <h3 className="font-display text-base font-medium text-slate-100">Control de secado</h3>
        </div>

        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3">
            <Metric label="T real" value={t.toFixed(1)} unit="°C" color="var(--temp)" big testid="secado-temp-metric" />
            <Metric label="HR real" value={hum.toFixed(1)} unit="%" color={humColor} big testid="secado-hum-metric" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Metric label="SP Temp" value={tObj.toFixed ? tObj.toFixed(1) : tObj} unit="°C" color="var(--amber)" testid="secado-sp-t" />
            <Metric label="SP HR" value={hObj.toFixed ? hObj.toFixed(1) : hObj} unit="%" color="var(--amber)" testid="secado-sp-h" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Metric label="Amb T" value={ambient?.temp?.toFixed(1) ?? '–'} unit="°C" color="var(--amber)" testid="secado-amb-t" />
            <Metric label="Amb HR" value={ambient?.humidity?.toFixed(1) ?? '–'} unit="%" color="var(--amber)" testid="secado-amb-h" />
          </div>

          <div className="space-y-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
            <NumberInput
              testid="secado-tobj"
              label="SP Temperatura"
              hint="Setpoint operativo (típico 90-100 °C)"
              unit="°C"
              value={tObj}
              onChange={(v) => { setTObj(v); apply({ temperatura_obj: v }); }}
              min={40} max={120} step={1}
            />
            <NumberInput
              testid="secado-hobj"
              label="SP Humedad final"
              hint="Piso de humedad que NO se puede bajar (7% típico)"
              unit="%"
              value={hObj}
              onChange={(v) => { setHObj(v); apply({ humedad_obj: v }); }}
              min={3} max={30} step={0.5}
            />
            <NumberInput
              testid="secado-tau"
              label="τ térmica"
              unit="s"
              value={tau}
              onChange={(v) => { setTau(v); apply({ tau_t: v }); }}
              min={5} max={1800} step={5}
            />
            <Slider
              testid="secado-aire-slider"
              label="Velocidad aire"
              value={aire}
              onChange={(v) => { setAire(v); apply({ velocidad_aire: v }); }}
              min={0} max={15} step={0.1} unit="m/s"
            />
            <div className="flex items-center justify-between pt-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Secador</span>
              <Toggle testid="secado-estado-toggle" value={estado} onChange={(v) => { setEstado(v); apply({ estado: v }); }} label={estado ? 'Activo' : 'Detenido'} />
            </div>
          </div>
        </div>
      </Card>

      <Card className="lg:col-span-3 p-0" testid="secado-chart-card">
        <CardHeader title="Histórico · Temperatura & humedad" subtitle="Piso dinámico HR = max(SP, 25% del ambiente)" />
        <div className="p-2 sm:p-4"><SecadoChart data={data} /></div>
      </Card>

      <div className="lg:col-span-3">
        <StageBlock stage="secado" state={state} />
      </div>

      <div className="lg:col-span-3">
        <FaultPanel
          title="Inyección de fallas · Secado"
          faults={faults}
          defs={[
            { key: 'falla_ventilador', label: 'Falla ventilador', hint: 'Sin circulación de aire: humedad no baja, T se acumula irregular.' },
            { key: 'falla_serpentin', label: 'Falla calefactor / serpentín', hint: 'No hay calor: T cae al ambiente, secado se detiene.' },
          ]}
          onApply={apply}
          testidBase="sec-fault"
        />
      </div>

      <Card className="lg:col-span-3 p-5" testid="secado-help">
        <SectionTitle kicker="?">¿Qué pasa en el secado?</SectionTitle>
        <p className="text-sm text-slate-300 mt-2 leading-relaxed">
          La yerba zapecada (~30-40% humedad) entra al secador de lecho. Aire calentado a ~95°C la atraviesa
          durante horas para bajar la humedad al 7% (umbral seguro contra hongos y rancidez). El proceso es lento:
          un descenso de humedad típico es 1-2%/hora.
        </p>
        <ul className="text-xs text-slate-400 font-mono mt-3 space-y-1.5 pl-3">
          <li>• <span className="text-amber-300">SP Temperatura</span>: bajalo a 85°C para secado suave (más tiempo, mejor color).</li>
          <li>• <span className="text-amber-300">SP Humedad final</span>: piso que no se puede bajar (7-9% típico).</li>
          <li>• <span className="text-amber-300">Velocidad aire</span>: a más m/s, más rápido el secado pero más consumo eléctrico.</li>
        </ul>
      </Card>
    </div>
  );
}

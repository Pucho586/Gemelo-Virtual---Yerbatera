import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Metric, Toggle, Slider, NumberInput, SectionTitle } from './UI';
import { CanchadoChart, flatten } from './Charts';
import { CanchadoMimic, CanchadoPid } from './Mimics';
import StageBlock from './StageBlock';
import FaultPanel from './FaultPanel';
import { api } from '../lib/api';
import { Cube } from '@phosphor-icons/react';

export default function CanchadoView({ state, series, mimicStyle = 'svg' }) {
  const c = state?.canchado;
  const faults = c?.faults || {};
  const [rpm, setRpm] = useState(c?.velocidad_molino ?? 60);
  const [estado, setEstado] = useState(c?.estado ?? true);
  const [pObj, setPObj] = useState(c?.tamano_particula_obj ?? '');
  const [tau, setTau] = useState(c?.tau_p ?? 5);

  useEffect(() => {
    if (c) {
      setRpm(c.velocidad_molino);
      setEstado(c.estado);
      setPObj(c.tamano_particula_obj ?? '');
      setTau(c.tau_p ?? 5);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [c?.velocidad_molino, c?.estado, c?.tamano_particula_obj, c?.tau_p]);

  const apply = async (patch) => {
    try { await api.patchCanchado(patch); } catch (e) { console.warn(e); }
  };

  const data = flatten(series);
  const p = c?.tamano_particula ?? 0;
  const pSp = c?.tamano_particula_sp_efectivo ?? 0;
  const pColor = p < 1 ? 'var(--red)' : p < 3.5 ? 'var(--orange)' : 'var(--green)';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-px hair-grid">
      <Card className="lg:col-span-2 p-0" testid="canchado-mimic-card">
        <CardHeader title="Canchado · Mímico" subtitle={mimicStyle === 'pid' ? 'P&ID' : 'Animación del molino'} />
        <div className="p-4">{mimicStyle === 'pid' ? <CanchadoPid data={c} /> : <CanchadoMimic data={c} />}</div>
      </Card>

      <Card className="p-6" testid="canchado-controls-card">
        <div className="flex items-center gap-2 mb-4">
          <Cube size={18} weight="duotone" className="text-purple-200" />
          <h3 className="font-display text-base font-medium text-slate-100">Molino</h3>
        </div>

        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3">
            <Metric label="Grosor real" value={p.toFixed(2)} unit="mm" color={pColor} big testid="canchado-particle-metric" />
            <Metric label="SP efectivo" value={pSp.toFixed(2)} unit="mm" color="var(--amber)" big testid="canchado-sp" />
          </div>
          <Metric label="Velocidad molino" value={rpm.toFixed(0)} unit="rpm" color="var(--text)" testid="canchado-rpm-metric" />

          <div className="space-y-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
            <NumberInput
              testid="canchado-pobj"
              label="SP Grosor canchada"
              hint="Vacío = automático según rpm (10 − 0.07·rpm). Con valor = SP fijo."
              unit="mm"
              value={pObj}
              onChange={(v) => { setPObj(v); apply({ tamano_particula_obj: v === '' || v == null ? null : v }); }}
              min={0} max={15} step={0.1}
            />
            <NumberInput
              testid="canchado-tau"
              label="τ molino"
              unit="s"
              value={tau}
              onChange={(v) => { setTau(v); apply({ tau_p: v }); }}
              min={0.5} max={120} step={0.5}
            />
            <Slider
              testid="canchado-rpm-slider"
              label="Velocidad molino"
              value={rpm}
              onChange={(v) => { setRpm(v); apply({ velocidad_molino: v }); }}
              min={0} max={130} step={1} unit="rpm"
            />
            <div className="flex items-center justify-between pt-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Canchador</span>
              <Toggle testid="canchado-estado-toggle" value={estado} onChange={(v) => { setEstado(v); apply({ estado: v }); }} label={estado ? 'Activo' : 'Detenido'} />
            </div>
          </div>
        </div>
      </Card>

      <Card className="lg:col-span-3 p-0" testid="canchado-chart-card">
        <CardHeader title="Histórico · Tamaño de partícula" subtitle="Target manual o dinámico = 10 − 0.07·rpm" />
        <div className="p-2 sm:p-4"><CanchadoChart data={data} /></div>
      </Card>

      <div className="lg:col-span-3">
        <StageBlock stage="canchado" state={state} />
      </div>

      <div className="lg:col-span-3">
        <FaultPanel
          title="Inyección de fallas · Canchado"
          faults={faults}
          defs={[
            { key: 'falla_motor', label: 'Falla motor molino', hint: 'El molino se detiene; encoder = 0 rpm; grosor queda congelado.' },
            { key: 'rodamiento_caliente', label: 'Rodamiento caliente', hint: 'Eleva T rodamientos (+35°C) y vibrómetro X (+4 mm/s) — alarma típica.' },
          ]}
          onApply={apply}
          testidBase="can-fault"
        />
      </div>

      <Card className="lg:col-span-3 p-5" testid="canchado-help">
        <SectionTitle kicker="?">¿Qué pasa en el canchado?</SectionTitle>
        <p className="text-sm text-slate-300 mt-2 leading-relaxed">
          Después del secado, la yerba pasa al molino canchador donde se la rompe en hojas/palos gruesos
          (3-10 mm). Este NO es el molido fino final, sino un troceado previo al estacionamiento. Cuanto más
          velocidad de molino, más fina la partícula.
        </p>
        <ul className="text-xs text-slate-400 font-mono mt-3 space-y-1.5 pl-3">
          <li>• <span className="text-amber-300">SP Grosor</span>: dejá vacío para automático; o fijá un valor (típico 4-8 mm).</li>
          <li>• <span className="text-red-300">Rodamiento caliente</span>: simulá una falla y andá a Mantenimiento para verla.</li>
        </ul>
      </Card>
    </div>
  );
}

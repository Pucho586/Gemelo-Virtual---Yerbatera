import React from 'react';
import { Card, CardHeader, Metric, Toggle, Slider, NumberInput, SectionTitle } from './UI';
import { CanchadoChart, flatten } from './Charts';
import { CanchadoMimic, CanchadoPid } from './Mimics';
import StageBlock from './StageBlock';
import FaultPanel from './FaultPanel';
import PidPanel from './PidPanel';
import { useLocalSync } from '../lib/useLocalSync';
import { api } from '../lib/api';
import { Cube } from '@phosphor-icons/react';

export default function CanchadoView({ state, series, mimicStyle = 'svg' }) {
  const c = state?.canchado;
  const faults = c?.faults || {};
  const [rpm, setRpm] = useLocalSync(c?.velocidad_molino ?? 60);
  const [estado, setEstado] = useLocalSync(c?.estado ?? true);
  const [pObj, setPObj] = useLocalSync(c?.tamano_particula_obj ?? '');
  const [tau, setTau] = useLocalSync(c?.tau_p ?? 5);

  const apply = async (patch) => {
    try { await api.patchCanchado(patch); } catch (e) { console.warn(e); }
  };

  const data = flatten(series);
  const p = c?.tamano_particula ?? 0;
  const pSp = c?.tamano_particula_sp_efectivo ?? 0;
  const rpmReal = c?.velocidad_molino_real ?? 0;
  const pColor = p < 1 ? 'var(--red)' : p < 3.5 ? 'var(--orange)' : 'var(--green)';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-px hair-grid">
      <Card className="lg:col-span-2 p-0" testid="canchado-mimic-card">
        <CardHeader title="Canchado · Mímico" subtitle="rpm REAL (no SP) — si apagás el molino se ve detenido" />
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
            <Metric label="SP grosor" value={pSp.toFixed(2)} unit="mm" color="var(--amber)" big testid="canchado-sp" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Metric label="rpm real" value={rpmReal.toFixed(0)} unit="rpm" color={rpmReal > 0 ? 'var(--green)' : 'var(--red)'} testid="canchado-rpm-real" />
            <Metric label="rpm SP" value={rpm.toFixed ? rpm.toFixed(0) : rpm} unit="rpm" color="var(--text)" testid="canchado-rpm-sp" />
          </div>

          <div className="space-y-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
            <NumberInput testid="canchado-pobj" label="SP Grosor canchada"
              hint="Vacío = automático según rpm (10 − 0.07·rpm)."
              unit="mm" value={pObj}
              onChange={(v) => { setPObj(v); apply({ tamano_particula_obj: v === '' || v == null ? null : v }); }}
              min={0} max={15} step={0.1} />
            <NumberInput testid="canchado-tau" label="τ molino" unit="s" value={tau}
              onChange={(v) => { setTau(v); apply({ tau_p: v }); }}
              min={0.5} max={120} step={0.5} />
            <Slider testid="canchado-rpm-slider" label="Velocidad molino (SP)" value={rpm}
              onChange={(v) => { setRpm(v); apply({ velocidad_molino: v }); }}
              min={0} max={130} step={1} unit="rpm" />
            <div className="flex items-center justify-between pt-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Canchador</span>
              <Toggle testid="canchado-estado-toggle" value={estado} onChange={(v) => { setEstado(v); apply({ estado: v }); }} label={estado ? 'Activo' : 'Detenido'} />
            </div>
          </div>
        </div>
      </Card>

      <Card className="lg:col-span-3 p-0" testid="canchado-chart-card">
        <CardHeader title="Histórico · Tamaño de partícula" subtitle="Apagá el molino y ve cómo la partícula queda congelada" />
        <div className="p-2 sm:p-4"><CanchadoChart data={data} /></div>
      </Card>

      <div className="lg:col-span-3">
        <StageBlock stage="canchado" state={state} />
      </div>

      <div className="lg:col-span-3">
        <PidPanel
          title="PID Canchado · ajusta rpm"
          pid={c?.pid}
          manipulada="vel. molino (rpm)"
          onApply={(patch) => apply({ pid: patch })}
          testidBase="can-pid"
        />
      </div>

      <div className="lg:col-span-3">
        <FaultPanel
          title="Inyección de fallas · Canchado"
          faults={faults}
          defs={[
            { key: 'falla_motor', label: 'Falla motor molino', hint: 'Molino detenido: encoder = 0 rpm, partícula queda congelada.' },
            { key: 'rodamiento_caliente', label: 'Rodamiento caliente', hint: 'Eleva T rodamientos (+35°C) y vibrómetro X (+4 mm/s).' },
          ]}
          onApply={apply}
          testidBase="can-fault"
        />
      </div>

      <Card className="lg:col-span-3 p-5" testid="canchado-help">
        <SectionTitle kicker="?">¿Qué pasa en el canchado?</SectionTitle>
        <ul className="text-xs text-slate-400 font-mono mt-2 space-y-1.5 pl-3 leading-relaxed">
          <li>• <span className="text-amber-300">rpm ↑</span>: partícula más fina (target = 10 − 0.07·rpm). Convergencia en τ segundos.</li>
          <li>• <span className="text-amber-300">Apagar molino</span>: rpm REAL = 0, partícula queda en el último valor.</li>
          <li>• <span className="text-amber-300">SP grosor</span>: dejá vacío para automático; fijo si querés ignorar rpm.</li>
        </ul>
      </Card>
    </div>
  );
}

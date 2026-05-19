import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Metric, Toggle, Slider } from './UI';
import { CanchadoChart, flatten } from './Charts';
import { CanchadoMimic, CanchadoPid } from './Mimics';
import StageBlock from './StageBlock';
import { api } from '../lib/api';
import { Cube } from '@phosphor-icons/react';

export default function CanchadoView({ state, series, mimicStyle = 'svg' }) {
  const c = state?.canchado;
  const [rpm, setRpm] = useState(c?.velocidad_molino ?? 60);
  const [estado, setEstado] = useState(c?.estado ?? true);

  useEffect(() => {
    if (c) {
      setRpm(c.velocidad_molino);
      setEstado(c.estado);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [c?.velocidad_molino, c?.estado]);

  const apply = async (patch) => {
    try { await api.patchCanchado(patch); } catch (e) { console.warn(e); }
  };

  const data = flatten(series);
  const p = c?.tamano_particula ?? 0;
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
          <Metric label="Tamaño partícula" value={p.toFixed(2)} unit="mm" color={pColor} big testid="canchado-particle-metric" />
          <Metric label="Velocidad molino" value={rpm.toFixed(0)} unit="rpm" color="var(--text)" testid="canchado-rpm-metric" />

          <div className="space-y-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
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
        <CardHeader title="Histórico · Tamaño de partícula" subtitle="Target = 10 − 0.07·rpm" />
        <div className="p-2 sm:p-4"><CanchadoChart data={data} /></div>
      </Card>

      <div className="lg:col-span-3">
        <StageBlock stage="canchado" state={state} />
      </div>
    </div>
  );
}

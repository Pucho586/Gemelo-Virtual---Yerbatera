import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Metric, Toggle, Slider } from './UI';
import { SecadoChart, flatten } from './Charts';
import { SecadoMimic, SecadoPid } from './Mimics';
import { api } from '../lib/api';
import { Drop, Wind } from '@phosphor-icons/react';

export default function SecadoView({ state, series, mimicStyle = 'svg' }) {
  const s = state?.secado;
  const ambient = state?.ambient;
  const [aire, setAire] = useState(s?.velocidad_aire ?? 2.5);
  const [estado, setEstado] = useState(s?.estado ?? true);

  useEffect(() => {
    if (s) {
      setAire(s.velocidad_aire);
      setEstado(s.estado);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s?.velocidad_aire, s?.estado]);

  const apply = async (patch) => {
    try { await api.patchSecado(patch); } catch (e) { console.warn(e); }
  };

  const data = flatten(series);
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
            <Metric label="Temperatura" value={(s?.temperatura ?? 0).toFixed(1)} unit="°C" color="var(--temp)" big testid="secado-temp-metric" />
            <Metric label="Humedad" value={hum.toFixed(1)} unit="%" color={humColor} big testid="secado-hum-metric" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Metric label="Ambiente T" value={ambient?.temp?.toFixed(1) ?? '–'} unit="°C" color="var(--amber)" testid="secado-amb-t" />
            <Metric label="Ambiente HR" value={ambient?.humidity?.toFixed(1) ?? '–'} unit="%" color="var(--amber)" testid="secado-amb-h" />
          </div>

          <div className="space-y-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
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
        <CardHeader title="Histórico · Temperatura & humedad" subtitle="Piso dinámico HR = 25% del ambiente" />
        <div className="p-2 sm:p-4"><SecadoChart data={data} /></div>
      </Card>
    </div>
  );
}

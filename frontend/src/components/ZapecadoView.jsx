import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Metric, Btn, Toggle, Slider, NumberInput } from './UI';
import { ZapecadoChart, flatten } from './Charts';
import { ZapecadoMimic, ZapecadoPid } from './Mimics';
import StageBlock from './StageBlock';
import { api } from '../lib/api';
import { Fire, Wind, Thermometer } from '@phosphor-icons/react';

export default function ZapecadoView({ state, series, mimicStyle = 'svg' }) {
  const z = state?.zapecado;
  const ambient = state?.ambient;
  const [tambor, setTambor] = useState(z?.velocidad_tambor ?? 15);
  const [chip, setChip] = useState(z?.velocidad_chip ?? 30);
  const [alim, setAlim] = useState(z?.estado_alimentacion ?? true);

  useEffect(() => {
    if (z) {
      setTambor(z.velocidad_tambor);
      setChip(z.velocidad_chip);
      setAlim(z.estado_alimentacion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [z?.velocidad_tambor, z?.velocidad_chip, z?.estado_alimentacion]);

  const apply = async (patch) => {
    try { await api.patchZapecado(patch); } catch (e) { console.warn(e); }
  };

  const t = z?.temperatura ?? 0;
  const tempColor = t > 580 ? 'var(--red)' : t > 540 ? 'var(--orange)' : 'var(--green)';
  const data = flatten(series);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-px hair-grid">
      <Card className="lg:col-span-2 p-0" testid="zapecado-mimic-card">
        <CardHeader title="Zapecado · Mímico en vivo" subtitle={mimicStyle === 'pid' ? 'Diagrama P&ID estilo industrial' : 'Vista esquemática animada del horno'} />
        <div className="p-4">
          {mimicStyle === 'pid' ? <ZapecadoPid data={z} /> : <ZapecadoMimic data={z} />}
        </div>
      </Card>

      <Card className="p-6" testid="zapecado-controls-card">
        <div className="flex items-center gap-2 mb-4">
          <Fire size={18} weight="duotone" className="text-red-300" />
          <h3 className="font-display text-base font-medium text-slate-100">Control del horno</h3>
        </div>

        <div className="space-y-5">
          <Metric label="Temperatura" value={t.toFixed(1)} unit="°C" color={tempColor} big testid="zapecado-temp-metric" />
          <div className="grid grid-cols-2 gap-3">
            <Metric label="Ambiente" value={ambient?.temp?.toFixed(1) ?? '–'} unit="°C" color="var(--amber)" testid="zapecado-ambient" />
            <Metric label="Estado" value={alim ? 'ON' : 'OFF'} color={alim ? 'var(--green)' : 'var(--red)'} testid="zapecado-state" />
          </div>

          <div className="space-y-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
            <Slider
              testid="zapecado-tambor-slider"
              label="Velocidad tambor"
              value={tambor}
              onChange={(v) => { setTambor(v); apply({ velocidad_tambor: v }); }}
              min={0} max={120} step={1} unit="rpm"
            />
            <Slider
              testid="zapecado-chip-slider"
              label="Velocidad chips"
              value={chip}
              onChange={(v) => { setChip(v); apply({ velocidad_chip: v }); }}
              min={0} max={200} step={1} unit="kg/h"
            />
            <div className="flex items-center justify-between pt-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Alimentación</span>
              <Toggle testid="zapecado-alim-toggle" value={alim} onChange={(v) => { setAlim(v); apply({ estado_alimentacion: v }); }} label={alim ? 'Activa' : 'Detenida'} />
            </div>
          </div>
        </div>
      </Card>

      <Card className="lg:col-span-3 p-0" testid="zapecado-chart-card">
        <CardHeader title="Histórico · Temperatura" subtitle="Setpoint dinámico 400-600°C según vel. de chips · ambiente Open-Meteo" action={<span className="font-mono text-[10px] text-slate-500">{data.length} pts</span>} />
        <div className="p-2 sm:p-4">
          <ZapecadoChart data={data} />
        </div>
      </Card>

      <div className="lg:col-span-3">
        <StageBlock stage="zapecado" state={state} />
      </div>
    </div>
  );
}

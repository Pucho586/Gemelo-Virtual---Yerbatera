import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Btn, NumberInput, SectionTitle, Metric } from './UI';
import { api } from '../lib/api';
import { useAuth, isAdmin } from '../lib/auth';
import { ArrowRight, Leaf, Thermometer, Drop, Scales, FlowArrow, ArrowsClockwise } from '@phosphor-icons/react';

const STAGE_INFO = {
  recepcion: { label: 'Recepción', desc: 'Pesaje de hoja verde (50-55% hum)', color: '#86EFAC' },
  zapecado: { label: 'Zapecado', desc: 'Inactivación enzimática (300-550°C, 3-5s)', color: '#FCA5A5' },
  secado: { label: 'Secado', desc: 'Reducción a 4-7% humedad (80-120°C, 3-8h)', color: '#FBBF24' },
  canchado: { label: 'Canchado', desc: 'Molienda gruesa (1-3 cm)', color: '#93C5FD' },
  estacionamiento: { label: 'Estacionamiento', desc: 'Maduración 6-24 meses o acelerada con vapor', color: '#C4B5FD' },
};

export default function MassFlowView() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [data, setData] = useState(null);
  const [cargaKg, setCargaKg] = useState(500);
  const [cargaT, setCargaT] = useState('');
  const [cargaH, setCargaH] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  const refresh = () => api.massflowGet().then(setData).catch(() => {});

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, []);

  const cargar = async () => {
    setErr('');
    if (cargaKg <= 0) { setErr('kg debe ser > 0'); return; }
    setLoading(true);
    try {
      const body = { kg: Number(cargaKg) };
      if (cargaT !== '') body.T = Number(cargaT);
      if (cargaH !== '') body.H = Number(cargaH);
      await api.massflowCarga(body.kg, body.T, body.H);
      refresh();
    } catch (e) { setErr(e?.response?.data?.detail || 'Error'); }
    finally { setLoading(false); }
  };

  const transferir = async (de, a) => {
    setErr('');
    try {
      await api.massflowTransferir(de, a);
      refresh();
    } catch (e) { setErr(e?.response?.data?.detail || 'Error'); }
  };

  const resetAll = async () => {
    if (!window.confirm('¿Resetear todo el flujo de masa? (no afecta lotes ni recetas)')) return;
    await api.massflowReset();
    refresh();
  };

  if (!data) return <div className="p-10 text-slate-500 font-mono">Cargando flujo de masa...</div>;

  const order = data.order || ['recepcion', 'zapecado', 'secado', 'canchado', 'estacionamiento'];

  return (
    <div className="space-y-px">
      {/* Info y carga */}
      <Card className="p-5" testid="massflow-info">
        <SectionTitle kicker="01">Trazabilidad de masa por etapa</SectionTitle>
        <p className="text-sm text-slate-400 mt-2">
          Cargá hoja verde en Recepción y movela manualmente a cada etapa con el botón <span className="text-amber-300 font-mono">→</span>.
          Cada transferencia aplica la merma típica de la etapa de origen y hereda T y H de salida (medidos por los sensores reales) como
          condiciones de entrada de la etapa siguiente.
        </p>
      </Card>

      <Card className="p-5" testid="massflow-carga">
        <div className="flex items-center justify-between mb-3">
          <SectionTitle kicker="02">Cargar hoja verde (entrada)</SectionTitle>
          {admin && <Btn testid="massflow-reset" variant="secondary" onClick={resetAll}>
            <span className="inline-flex items-center gap-1"><ArrowsClockwise size={12}/> Reset flujo</span>
          </Btn>}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <NumberInput testid="carga-kg" label="kg a cargar" value={cargaKg} onChange={setCargaKg} min={1} max={50000} step={50} />
          <NumberInput testid="carga-t" label="T hoja (opc)" unit="°C" value={cargaT} onChange={setCargaT} step={0.5} />
          <NumberInput testid="carga-h" label="Humedad (opc)" unit="%" value={cargaH} onChange={setCargaH} min={30} max={70} step={1} />
          <Btn testid="carga-confirm" onClick={cargar} disabled={loading}>
            <span className="inline-flex items-center gap-1"><Leaf size={13}/> {loading ? 'Cargando...' : 'Cargar a Recepción'}</span>
          </Btn>
        </div>
        <p className="text-[11px] font-mono text-slate-500 mt-2">
          Sin T/H se usan: T = ambiente actual ({/* shown via state */}clima), H = 55% (típica hoja recién cosechada).
        </p>
        {err && <div className="mt-2 px-3 py-2 text-xs font-mono bg-red-500/10 text-red-300 border border-red-500/30" data-testid="massflow-err">{err}</div>}
      </Card>

      {/* Pipeline visual */}
      <Card className="p-0" testid="massflow-pipeline">
        <CardHeader title="Pipeline en vivo" subtitle="kg actual, acumulados, T y H de cada etapa · refrescado cada 3s" />
        <div className="p-4 overflow-x-auto">
          <div className="flex items-stretch gap-2 min-w-max">
            {order.map((stage, i) => {
              const s = data.stages[stage];
              const info = STAGE_INFO[stage] || { label: stage, desc: '', color: 'var(--amber)' };
              const merma_pct = data.merma_pct[stage] || 0;
              const nextStage = order[i + 1];
              return (
                <React.Fragment key={stage}>
                  <div className="surface p-4 min-w-[220px] flex-1" data-testid={`stage-${stage}`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-display text-sm font-medium" style={{ color: info.color }}>{info.label}</div>
                      <span className="text-[10px] font-mono text-slate-500">#{i + 1}</span>
                    </div>
                    <p className="text-[10px] font-mono text-slate-500 mb-3 leading-snug">{info.desc}</p>
                    <div className="space-y-1.5">
                      <div className="flex justify-between font-mono text-xs">
                        <span className="text-slate-500">kg actual</span>
                        <span className="text-slate-100 font-medium" data-testid={`stage-${stage}-kg`}>{s.kg_actual.toFixed(1)}</span>
                      </div>
                      <div className="flex justify-between font-mono text-[10px] text-slate-400">
                        <span>acum in</span><span>{s.kg_acum_in.toFixed(1)} kg</span>
                      </div>
                      <div className="flex justify-between font-mono text-[10px] text-slate-400">
                        <span>acum out</span><span>{s.kg_acum_out.toFixed(1)} kg</span>
                      </div>
                      <div className="flex justify-between font-mono text-[10px] text-red-300/80">
                        <span>merma</span><span>{s.merma_kg_acum.toFixed(1)} kg ({(merma_pct * 100).toFixed(1)}%)</span>
                      </div>
                      <div className="border-t pt-1.5 mt-1.5 grid grid-cols-2 gap-1" style={{ borderColor: 'var(--border)' }}>
                        <div className="font-mono text-[10px]">
                          <span className="text-slate-500">T in: </span>
                          <span className="text-amber-300" data-testid={`stage-${stage}-tin`}>{s.T_in != null ? `${s.T_in.toFixed(1)}°C` : '—'}</span>
                        </div>
                        <div className="font-mono text-[10px]">
                          <span className="text-slate-500">H in: </span>
                          <span className="text-blue-300" data-testid={`stage-${stage}-hin`}>{s.H_in != null ? `${s.H_in.toFixed(1)}%` : '—'}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  {nextStage && (
                    <div className="flex flex-col items-center justify-center gap-1 pt-12">
                      <button
                        data-testid={`xfer-${stage}-${nextStage}`}
                        onClick={() => transferir(stage, nextStage)}
                        disabled={s.kg_actual <= 0}
                        className="px-2 py-3 border text-amber-300 hover:bg-amber-500/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        style={{ borderColor: 'var(--border)' }}
                        title={`Transferir ${s.kg_actual.toFixed(0)} kg a ${STAGE_INFO[nextStage]?.label}`}
                      >
                        <ArrowRight size={16}/>
                      </button>
                      <span className="text-[9px] font-mono text-slate-600">pasar</span>
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </Card>

      {/* Sensores reales (info) */}
      <Card className="p-5" testid="massflow-sensores">
        <SectionTitle kicker="03">Puntos de medición (sensores reales en planta)</SectionTitle>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
          <div className="surface p-3">
            <div className="text-red-300 mb-1 font-medium">Zapecado</div>
            <ul className="space-y-1 text-slate-300 leading-relaxed">
              <li>• <span className="text-amber-300">Termocupla tipo K</span> en entrada de tambor (T gases de combustión, 300-550°C)</li>
              <li>• <span className="text-amber-300">Termocupla tipo K</span> en salida (T de la yerba zapecada, ~110-130°C)</li>
              <li>• <span className="text-blue-300">Sensor capacitivo o NIR</span> a la salida (H 22-30%)</li>
              <li>• Vibrómetro en eje del tambor (mantenimiento)</li>
            </ul>
          </div>
          <div className="surface p-3">
            <div className="text-amber-300 mb-1 font-medium">Secadero (banda o rotativo)</div>
            <ul className="space-y-1 text-slate-300 leading-relaxed">
              <li>• <span className="text-amber-300">PT100 o termocupla K</span> en aire de entrada (80-120°C)</li>
              <li>• <span className="text-amber-300">PT100</span> en aire de salida y cintas/cilindro (control de zona)</li>
              <li>• <span className="text-blue-300">Higrómetro NIR infrarrojo</span> en salida — medición de humedad final 4-7%</li>
              <li>• <span className="text-blue-300">Higrómetro bulbo húmedo</span> en aire de extracción</li>
            </ul>
          </div>
          <div className="surface p-3">
            <div className="text-blue-300 mb-1 font-medium">Canchado</div>
            <ul className="space-y-1 text-slate-300 leading-relaxed">
              <li>• <span className="text-amber-300">PT100</span> en carcasa de rodamientos del molino (mantenimiento predictivo)</li>
              <li>• Vibrómetro 3 ejes en bancada</li>
              <li>• Encoder de velocidad del rotor</li>
              <li>• <span className="text-blue-300">Higrómetro NIR</span> opcional a la salida (verifica que el secado fue correcto)</li>
            </ul>
          </div>
          <div className="surface p-3">
            <div className="text-violet-300 mb-1 font-medium">Estacionamiento / Cámara de maduración</div>
            <ul className="space-y-1 text-slate-300 leading-relaxed">
              <li>• <span className="text-amber-300">PT100 doble</span>: uno en pared, uno en el centro de la pila de yerba</li>
              <li>• <span className="text-blue-300">Sensor capacitivo</span> de humedad relativa (40-90%)</li>
              <li>• <span className="text-green-300">Sensor NDIR</span> de CO₂ (la yerba respira durante el añejado)</li>
              <li>• Termoresistencia en línea de vapor (si hay inyección)</li>
              <li>• Caudalímetro de vapor (kg/h) en aprovisionamiento de la caldera</li>
            </ul>
          </div>
        </div>
        <p className="text-[10px] font-mono text-slate-500 mt-3 leading-relaxed">
          Referencias: INYM (Instituto Nacional de la Yerba Mate), normativa Mercosur RTM RES GMC 24/13,
          literatura técnica de Andina S.A. y CARP S.A. La variante exacta de instrumentación depende de cada
          planta y antigüedad del equipamiento.
        </p>
      </Card>

      {/* Log de eventos */}
      <Card className="p-0" testid="massflow-log">
        <CardHeader title="Log de eventos (últimos 50)" subtitle="Cargas, transferencias y mermas registradas" />
        <div className="max-h-64 overflow-y-auto">
          {(data.log_recent || []).slice().reverse().map((ev, i) => (
            <div key={i} className="px-4 py-2 border-b last:border-b-0 font-mono text-[11px] text-slate-300 flex flex-wrap gap-x-3" style={{ borderColor: 'var(--border)' }} data-testid={`log-${i}`}>
              <span className="text-slate-500">{ev.ts?.slice(11, 19)}</span>
              {ev.action === 'carga_hoja_verde' ? (
                <span><span className="text-green-400">CARGA</span> · {ev.kg} kg · T={ev.T?.toFixed(1)}°C H={ev.H?.toFixed(1)}% · <span className="text-slate-500">{ev.user}</span></span>
              ) : (
                <span>
                  <span className="text-amber-300">{ev.de}</span> → <span className="text-amber-300">{ev.a}</span> ·
                  in={ev.kg_in} kg → out={ev.kg_out} kg (merma {ev.merma_kg} kg, {(ev.merma_pct * 100).toFixed(1)}%) ·
                  T_out={ev.T_out}°C H_out={ev.H_out}% · <span className="text-slate-500">{ev.user}</span>
                </span>
              )}
            </div>
          ))}
          {(!data.log_recent || data.log_recent.length === 0) && (
            <div className="px-4 py-6 font-mono text-xs text-slate-500 text-center">Sin eventos. Cargá hoja verde para empezar.</div>
          )}
        </div>
      </Card>
    </div>
  );
}

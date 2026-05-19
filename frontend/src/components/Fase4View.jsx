import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Btn, NumberInput, TextInput, SectionTitle, Metric, StatusBadge } from './UI';
import { api } from '../lib/api';
import { useAuth, isAdmin } from '../lib/auth';
import { Rewind, PlayCircle, PauseCircle, Stop, FastForward, Flask, Plus, Trash, Broadcast } from '@phosphor-icons/react';

export default function Fase4View() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [tab, setTab] = useState('replay');

  return (
    <div className="space-y-px">
      <Card className="p-0" testid="fase4-tabs">
        <div className="flex flex-wrap border-b" style={{ borderColor: 'var(--border)' }}>
          {[
            ['replay', 'Replay histórico', Rewind],
            ['whatif', 'What-if (escenarios)', Flask],
          ].map(([k, l, Ic]) => (
            <button key={k} data-testid={`fase4-tab-${k}`} onClick={() => setTab(k)}
              className={`px-4 py-2.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 ${tab === k ? 'border-amber-300 text-slate-100' : 'border-transparent text-slate-400 hover:text-slate-200'}`}>
              <Ic size={13} /> {l}
            </button>
          ))}
        </div>
      </Card>
      {tab === 'replay' && <ReplayPanel admin={admin} />}
      {tab === 'whatif' && <WhatIfPanel admin={admin} />}
    </div>
  );
}

// ============================ REPLAY ============================
function ReplayPanel({ admin }) {
  const [files, setFiles] = useState([]);
  const [status, setStatus] = useState({ active: false });
  const [selectedFile, setSelectedFile] = useState('');
  const [speed, setSpeed] = useState(10);

  const refresh = () => Promise.all([
    api.replayFiles().then(setFiles).catch(() => {}),
    api.replayStatus().then(setStatus).catch(() => {}),
  ]);

  useEffect(() => {
    refresh();
    const id = setInterval(() => api.replayStatus().then(setStatus).catch(() => {}), 1500);
    return () => clearInterval(id);
  }, []);

  const start = async () => {
    if (!selectedFile) return;
    try { await api.replayStart({ file: selectedFile, speed }); refresh(); }
    catch (e) { alert(e?.response?.data?.detail || 'Error'); }
  };
  const stop = async () => { await api.replayStop(); refresh(); };
  const togglePause = async () => { await api.replayPause(!status.paused); refresh(); };
  const seek = async (pct) => {
    const row = Math.floor(pct * (status.total || 0));
    await api.replaySeek(row);
    refresh();
  };
  const changeSpeed = async (s) => { setSpeed(s); if (status.active) await api.replaySpeed(s); };

  return (
    <div className="space-y-px">
      <Card className="p-5" testid="replay-info">
        <SectionTitle kicker="01">Modo Replay (entrenamiento con datos reales)</SectionTitle>
        <p className="text-sm text-slate-400 mt-2">
          Cargá un CSV histórico del proceso y reproducilo a la velocidad que necesites.
          El gemelo digital alimenta el estado desde el archivo en lugar de calcularlo matemáticamente.
          Ideal para certificar operarios con eventos reales del pasado.
        </p>
        {status.active && (
          <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 text-xs font-mono uppercase tracking-wider border bg-amber-500/10 text-amber-300 border-amber-500/40" data-testid="replay-mode-badge">
            <Broadcast size={12}/> Modo REPLAY activo · {status.file} · {(status.progress * 100).toFixed(1)}%
          </div>
        )}
      </Card>

      <Card className="p-5" testid="replay-controls">
        <SectionTitle kicker="02">Controles</SectionTitle>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Archivo histórico</label>
            <select
              data-testid="replay-file-select"
              className="field w-full mt-1"
              value={selectedFile}
              onChange={(e) => setSelectedFile(e.target.value)}
              disabled={status.active}
            >
              <option value="">— Elegí un CSV —</option>
              {files.map(f => (
                <option key={f.name} value={f.name}>{`${f.name} (${(f.size / 1024).toFixed(1)} KB)`}</option>
              ))}
            </select>
          </div>
          <NumberInput testid="replay-speed" label="Velocidad" unit="×" value={speed} onChange={changeSpeed} min={0.25} max={120} step={0.25} />
          <div className="flex items-end gap-2">
            {!status.active && admin && (
              <Btn testid="replay-start-btn" onClick={start} disabled={!selectedFile}>
                <span className="inline-flex items-center gap-1"><PlayCircle size={13}/> Iniciar</span>
              </Btn>
            )}
            {status.active && admin && (
              <>
                <Btn testid="replay-pause-btn" variant="secondary" onClick={togglePause}>
                  <span className="inline-flex items-center gap-1">{status.paused ? <PlayCircle size={13}/> : <PauseCircle size={13}/>} {status.paused ? 'Reanudar' : 'Pausar'}</span>
                </Btn>
                <Btn testid="replay-stop-btn" variant="danger" onClick={stop}>
                  <span className="inline-flex items-center gap-1"><Stop size={13}/> Detener</span>
                </Btn>
              </>
            )}
          </div>
        </div>

        {status.active && (
          <div className="mt-5 space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-px hair-grid">
              <div className="surface p-3"><Metric label="Fila actual" value={status.cursor} unit={`/ ${status.total}`} testid="replay-cursor" /></div>
              <div className="surface p-3"><Metric label="Progreso" value={(status.progress * 100).toFixed(1)} unit="%" color="var(--amber)" /></div>
              <div className="surface p-3"><Metric label="Velocidad" value={status.speed} unit="×" /></div>
              <div className="surface p-3"><Metric label="Estado" value={status.paused ? 'PAUSADO' : 'CORRIENDO'} color={status.paused ? '#FCA5A5' : '#86EFAC'} /></div>
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Timeline (clic para ir a una posición)</label>
              <input
                type="range"
                data-testid="replay-timeline"
                min={0}
                max={1000}
                value={Math.floor(status.progress * 1000)}
                onChange={(e) => seek(Number(e.target.value) / 1000)}
                className="w-full mt-2 accent-amber-300"
              />
              <p className="font-mono text-[11px] text-slate-500 mt-1">TS: {status.ts_at_cursor || '—'}</p>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

// ============================ WHAT-IF ============================
function WhatIfPanel({ admin }) {
  const [scenarios, setScenarios] = useState([]);
  const [newName, setNewName] = useState('');
  const [newOverridesJson, setNewOverridesJson] = useState('{\n  "secado": { "temperatura_setpoint": 105 },\n  "throughput_kgh": 600\n}');
  const [creating, setCreating] = useState(false);
  const [baselineState, setBaselineState] = useState(null);

  const refresh = () => Promise.all([
    api.whatifList().then(setScenarios).catch(() => {}),
    api.getState().then(setBaselineState).catch(() => {}),
  ]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 2500);
    return () => clearInterval(id);
  }, []);

  const create = async () => {
    if (!newName.trim()) { alert('Nombre requerido'); return; }
    let overrides = {};
    try { overrides = JSON.parse(newOverridesJson); }
    catch (e) { alert('JSON inválido en overrides: ' + e.message); return; }
    setCreating(true);
    try {
      await api.whatifCreate({ name: newName.trim(), overrides });
      setNewName('');
      refresh();
    } catch (e) {
      alert(e?.response?.data?.detail || 'Error al crear');
    } finally {
      setCreating(false);
    }
  };

  const del = async (id) => {
    if (!window.confirm(`¿Eliminar escenario ${id}?`)) return;
    await api.whatifDelete(id);
    refresh();
  };

  const resetAll = async () => {
    if (!window.confirm('¿Eliminar TODOS los escenarios?')) return;
    await api.whatifResetAll();
    refresh();
  };

  // Construir tabla comparativa: baseline + cada escenario
  const baselineKpis = baselineState ? {
    TempZapecado: baselineState.zapecado?.temperatura,
    TempSecado: baselineState.secado?.temperatura,
    HumFinal: baselineState.secado?.humedad,
    Throughput: baselineState.throughput_kgh,
  } : {};

  return (
    <div className="space-y-px">
      <Card className="p-5" testid="whatif-info">
        <SectionTitle kicker="01">Escenarios "What-if" en paralelo</SectionTitle>
        <p className="text-sm text-slate-400 mt-2">
          Corré hasta 3 simulaciones paralelas con parámetros distintos del baseline para comparar OEE,
          costos, calidad y consumo. Cada escenario expone sus KPIs en:
        </p>
        <ul className="text-xs font-mono text-slate-400 mt-2 space-y-1 pl-4">
          <li>· <span className="text-amber-300">Modbus TCP</span> → unit IDs 20, 21, 22 (registros HR 0-7)</li>
          <li>· <span className="text-amber-300">OPC UA</span> → /Plant/WhatIf/{`scenarioN`}/{`{OEE,CostoPorKg,kWhAcum,...}`}</li>
          <li>· <span className="text-amber-300">MQTT</span> → topics <code>yerba/whatif/scenarioN/{`{kpi}`}</code></li>
        </ul>
      </Card>

      {admin && (
        <Card className="p-5" testid="whatif-create">
          <SectionTitle kicker="02">Crear escenario</SectionTitle>
          <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
            <TextInput testid="whatif-name" label="Nombre" value={newName} onChange={setNewName} placeholder="Ej: Secado a 105°C" />
            <div className="md:col-span-2">
              <label className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Overrides (JSON · ej: {`{"zapecado":{"velocidad_chip":20}}`})</label>
              <textarea
                data-testid="whatif-overrides-json"
                className="field w-full mt-1 font-mono text-xs"
                rows={5}
                value={newOverridesJson}
                onChange={(e) => setNewOverridesJson(e.target.value)}
              />
            </div>
            <div className="md:col-span-3 flex justify-between items-center">
              <p className="text-[11px] font-mono text-slate-500">Máximo 3 escenarios paralelos. Cambiar requiere borrar primero.</p>
              <div className="flex gap-2">
                {scenarios.length > 0 && <Btn testid="whatif-reset-all" variant="secondary" onClick={resetAll}><span className="inline-flex items-center gap-1"><Trash size={12}/> Reset todos</span></Btn>}
                <Btn testid="whatif-create-btn" onClick={create} disabled={creating || scenarios.length >= 3}>
                  <span className="inline-flex items-center gap-1"><Plus size={12}/> {creating ? 'Creando...' : 'Crear escenario'}</span>
                </Btn>
              </div>
            </div>
          </div>
        </Card>
      )}

      <Card className="p-0" testid="whatif-compare-table">
        <CardHeader title="Comparativa en vivo" subtitle="KPIs por escenario refrescados cada 2.5s · baseline + variantes" />
        {scenarios.length === 0 ? (
          <div className="p-5 font-mono text-xs text-slate-500">Sin escenarios. Creá uno arriba para empezar a comparar.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <th className="text-left px-4 py-2 text-[10px] uppercase tracking-wider text-slate-500">KPI</th>
                  <th className="text-right px-4 py-2 text-[10px] uppercase tracking-wider text-slate-300">Baseline</th>
                  {scenarios.map((s) => (
                    <th key={s.id} className="text-right px-4 py-2 text-[10px] uppercase tracking-wider text-amber-300" data-testid={`whatif-th-${s.id}`}>
                      {s.name} <span className="text-slate-500 text-[9px]">({s.id})</span>
                    </th>
                  ))}
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['OEE', '%', baselineKpis.TempZapecado != null ? '—' : '—'],
                  ['CostoPorKg', 'ARS', '—'],
                  ['kWhAcum', 'kWh', '—'],
                  ['ChipsKgAcum', 'kg', '—'],
                  ['TempZapecado', '°C', baselineState?.zapecado?.temperatura?.toFixed(1)],
                  ['TempSecado', '°C', baselineState?.secado?.temperatura?.toFixed(1)],
                  ['HumFinal', '%', baselineState?.secado?.humedad?.toFixed(1)],
                  ['ProduccionKg', 'kg', '—'],
                ].map(([kpi, unit, base], i) => (
                  <tr key={kpi} className="border-b last:border-b-0" style={{ borderColor: 'var(--border)' }} data-testid={`whatif-row-${kpi}`}>
                    <td className="text-left px-4 py-1.5 text-slate-300">{kpi} <span className="text-slate-600">({unit})</span></td>
                    <td className="text-right px-4 py-1.5 text-slate-200">{base}</td>
                    {scenarios.map((s) => {
                      const v = s.kpis?.[kpi];
                      const numericBase = parseFloat(base);
                      let cls = 'text-slate-100';
                      if (typeof v === 'number' && !Number.isNaN(numericBase)) {
                        const delta = v - numericBase;
                        if (kpi === 'OEE' || kpi === 'ProduccionKg') {
                          cls = delta > 0 ? 'text-green-400' : delta < 0 ? 'text-red-400' : 'text-slate-100';
                        } else if (kpi === 'CostoPorKg' || kpi === 'kWhAcum' || kpi === 'ChipsKgAcum' || kpi === 'HumFinal') {
                          cls = delta < 0 ? 'text-green-400' : delta > 0 ? 'text-red-400' : 'text-slate-100';
                        }
                      }
                      return (
                        <td key={s.id} className={`text-right px-4 py-1.5 ${cls}`} data-testid={`whatif-cell-${s.id}-${kpi}`}>
                          {typeof v === 'number' ? v.toFixed(2) : '—'}
                        </td>
                      );
                    })}
                    {i === 0 && (
                      <td rowSpan={8} className="text-right px-4 py-1.5 align-top">
                        {admin && scenarios.map((s) => (
                          <button key={s.id} onClick={() => del(s.id)} className="block text-red-400 hover:text-red-300 mb-1" data-testid={`whatif-del-${s.id}`}>
                            <Trash size={12}/>
                          </button>
                        ))}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-3 border-t font-mono text-[10px] text-slate-500" style={{ borderColor: 'var(--border)' }}>
              Verde = mejor que baseline · Rojo = peor que baseline. Para OEE y producción "más" es mejor; para costos, kWh, chips y humedad final, "menos" es mejor.
            </div>
          </div>
        )}
      </Card>

      <Card className="p-5" testid="whatif-scada-info">
        <SectionTitle kicker="·">Lectura desde PLC / SCADA</SectionTitle>
        <p className="text-xs text-slate-400 mt-2 font-mono">
          Cada escenario está disponible en tiempo real. Por ejemplo para escenario1:
        </p>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px] font-mono">
          <div className="surface p-3">
            <div className="text-amber-300 mb-1">Modbus TCP · unit 20</div>
            <div className="text-slate-300">HR[0] = OEE × 10</div>
            <div className="text-slate-300">HR[1] = $/kg × 10</div>
            <div className="text-slate-300">HR[2] = kWh × 10</div>
            <div className="text-slate-300">HR[3] = Chips kg × 10</div>
            <div className="text-slate-300">HR[4] = T zapecado × 10</div>
            <div className="text-slate-300">HR[5] = T secado × 10</div>
            <div className="text-slate-300">HR[6] = HR final × 10</div>
            <div className="text-slate-300">HR[7] = Producción kg</div>
          </div>
          <div className="surface p-3">
            <div className="text-amber-300 mb-1">OPC UA</div>
            <div className="text-slate-300">/Plant/WhatIf/scenario1/OEE</div>
            <div className="text-slate-300">/Plant/WhatIf/scenario1/CostoPorKg</div>
            <div className="text-slate-300">/Plant/WhatIf/scenario1/...</div>
          </div>
          <div className="surface p-3">
            <div className="text-amber-300 mb-1">MQTT</div>
            <div className="text-slate-300">yerba/whatif/scenario1/OEE</div>
            <div className="text-slate-300">yerba/whatif/scenario1/CostoPorKg</div>
            <div className="text-slate-300">yerba/whatif/scenario1/...</div>
          </div>
        </div>
      </Card>
    </div>
  );
}

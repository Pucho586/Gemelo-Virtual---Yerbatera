import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Btn, NumberInput, SectionTitle, Metric, StatusBadge } from './UI';
import { api } from '../lib/api';
import { useAuth, isAdmin } from '../lib/auth';
import {
  Bell, Gauge, Wrench, Lightning, FileArrowDown, CheckCircle, Warning,
  CurrencyCircleDollar, Clock, Factory, FilePdf,
} from '@phosphor-icons/react';

export default function OperacionesView() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [tab, setTab] = useState('alarms');

  return (
    <div className="space-y-px">
      <Card className="p-0" testid="ops-tabs">
        <div className="flex flex-wrap border-b" style={{ borderColor: 'var(--border)' }}>
          {[
            ['alarms', 'Alarmas', Bell],
            ['oee', 'OEE', Gauge],
            ['maint', 'Mantenimiento', Wrench],
            ['energy', 'Energía & Costos', Lightning],
            ['reports', 'Reportes PDF', FilePdf],
          ].map(([k, l, Ic]) => (
            <button key={k} data-testid={`ops-tab-${k}`} onClick={() => setTab(k)}
              className={`px-4 py-2.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 ${tab === k ? 'border-amber-300 text-slate-100' : 'border-transparent text-slate-400 hover:text-slate-200'}`}>
              <Ic size={13}/> {l}
            </button>
          ))}
        </div>
      </Card>

      {tab === 'alarms' && <AlarmsPanel admin={admin} />}
      {tab === 'oee' && <OeePanel />}
      {tab === 'maint' && <MaintPanel admin={admin} />}
      {tab === 'energy' && <EnergyPanel admin={admin} />}
      {tab === 'reports' && <ReportsPanel />}
    </div>
  );
}

// ============================ ALARMS ============================
function priorityCls(p) {
  return p === 'urgent' ? 'border-red-500/50 bg-red-500/10 text-red-300' :
         p === 'high'   ? 'border-amber-500/50 bg-amber-500/10 text-amber-300' :
         p === 'medium' ? 'border-yellow-500/40 bg-yellow-500/5 text-yellow-200' :
                          'border-slate-500/30 bg-slate-500/5 text-slate-300';
}

function AlarmsPanel({ admin }) {
  const [active, setActive] = useState([]);
  const [history, setHistory] = useState([]);

  const load = async () => {
    setActive(await api.alarmsActive());
    setHistory(await api.alarmsHistory(100));
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, []);

  const ack = async (alarmId) => {
    try { await api.alarmAck(alarmId); await load(); }
    catch (e) { alert(e?.response?.data?.detail || 'Error'); }
  };

  const counts = {
    urgent: active.filter(a => a.priority === 'urgent').length,
    high: active.filter(a => a.priority === 'high').length,
    medium: active.filter(a => a.priority === 'medium').length,
    low: active.filter(a => a.priority === 'low').length,
  };

  return (
    <div className="space-y-px">
      <Card className="p-5" testid="alarms-summary">
        <SectionTitle kicker="01">Alarmas activas (ISA-18.2)</SectionTitle>
        <div className="grid grid-cols-4 gap-3 mt-3">
          {[['urgent', 'Urgentes'], ['high', 'Altas'], ['medium', 'Medias'], ['low', 'Bajas']].map(([k, l]) => (
            <div key={k} className={`border-l-2 p-3 ${priorityCls(k)}`} data-testid={`alarms-count-${k}`}>
              <div className="font-mono text-[10px] uppercase tracking-wider opacity-70">{l}</div>
              <div className="font-mono text-2xl font-light">{counts[k]}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-0" testid="alarms-active-list">
        <CardHeader title="Activas (requieren atención)" subtitle="Reconocer (ACK) las alarmas para reducir ruido en planta" />
        {active.length === 0 ? (
          <div className="p-5 font-mono text-xs text-green-400 inline-flex items-center gap-2"><CheckCircle size={14}/> Sin alarmas activas. Todo en orden.</div>
        ) : (
          <div>
            {active.map((a) => (
              <div key={a.id} className={`border-l-4 px-4 py-3 flex items-center gap-4 border-b last:border-b-0 ${priorityCls(a.priority)}`} style={{ borderBottomColor: 'var(--border)' }} data-testid={`alarm-row-${a.id}`}>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] uppercase tracking-wider opacity-90">{a.priority}</span>
                    <span className="font-display text-sm text-slate-100">{a.name}</span>
                  </div>
                  <div className="font-mono text-[11px] text-slate-400 mt-0.5">
                    {a.tag} · {a.op} {a.threshold} · valor disparador: {a.value_at_trigger}
                    {a.last_value != null && <> · actual: <span className="text-amber-300">{a.last_value}</span></>}
                  </div>
                  <div className="font-mono text-[10px] text-slate-500 mt-0.5">{new Date(a.ts).toLocaleString()} · {a.status}</div>
                </div>
                <Btn testid={`alarm-ack-${a.id}`} variant={a.status === 'unacked_active' ? 'ai' : 'secondary'} onClick={() => ack(a.id)}>
                  {a.status === 'acked_active' ? 'Acked' : a.status === 'unacked_rtn' ? 'ACK & Clear' : 'ACK'}
                </Btn>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-0" testid="alarms-history-card">
        <CardHeader title="Historial" subtitle="Últimas 100 alarmas" />
        <div className="overflow-x-auto">
          <div className="grid grid-cols-6 gap-2 px-4 py-2 border-b font-mono text-[10px] uppercase tracking-wider text-slate-500" style={{ borderColor: 'var(--border)' }}>
            <span>Fecha</span><span>Prio</span><span>Alarma</span><span>Tag</span><span>Estado</span><span>ACK</span>
          </div>
          {history.map((a, i) => (
            <div key={i} className="grid grid-cols-6 gap-2 px-4 py-1.5 border-b last:border-b-0 font-mono text-xs" style={{ borderColor: 'var(--border)' }} data-testid={`alarm-hist-${i}`}>
              <span className="text-slate-400">{new Date(a.ts).toLocaleString()}</span>
              <span className={priorityCls(a.priority).split(' ')[2]}>{a.priority}</span>
              <span className="text-slate-200 truncate">{a.name}</span>
              <span className="text-slate-400 truncate">{a.tag}</span>
              <span className="text-slate-300">{a.status}</span>
              <span className="text-amber-300">{a.acked_by || '—'}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ============================ OEE ============================
function OeePanel() {
  const [oee, setOee] = useState(null);
  useEffect(() => {
    const load = () => api.getOee(24).then(setOee).catch(() => {});
    load();
    const id = setInterval(load, 6000);
    return () => clearInterval(id);
  }, []);
  if (!oee) return <div className="p-10 text-slate-500 font-mono">Calculando OEE...</div>;

  const v = oee.oee * 100;
  const cls = v > 85 ? 'var(--green)' : v > 60 ? 'var(--amber)' : 'var(--red)';

  return (
    <div className="space-y-px">
      <Card className="p-5" testid="oee-headline">
        <SectionTitle kicker="01">Overall Equipment Effectiveness</SectionTitle>
        <div className="flex items-center justify-center py-8">
          <div className="text-center">
            <div className="font-mono text-7xl font-light" style={{ color: cls }} data-testid="oee-value">{v.toFixed(1)}%</div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500 mt-2">OEE total · ventana 24h</div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-px hair-grid">
          <div className="surface p-5 text-center" data-testid="oee-availability">
            <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500">Disponibilidad</div>
            <div className="font-mono text-3xl font-light text-slate-100 mt-1">{(oee.availability * 100).toFixed(1)}%</div>
            <div className="font-mono text-xs text-slate-500 mt-1">{oee.operativas_h.toFixed(1)}h operativas</div>
          </div>
          <div className="surface p-5 text-center" data-testid="oee-performance">
            <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500">Rendimiento</div>
            <div className="font-mono text-3xl font-light text-slate-100 mt-1">{(oee.performance * 100).toFixed(1)}%</div>
            <div className="font-mono text-xs text-slate-500 mt-1">{oee.produccion_kg.toFixed(0)} kg producidos</div>
          </div>
          <div className="surface p-5 text-center" data-testid="oee-quality">
            <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500">Calidad</div>
            <div className="font-mono text-3xl font-light text-slate-100 mt-1">{(oee.quality * 100).toFixed(1)}%</div>
            <div className="font-mono text-xs text-slate-500 mt-1">kg buenos / kg totales</div>
          </div>
        </div>
        <p className="font-mono text-[11px] text-slate-500 mt-4 text-center">
          OEE = Disponibilidad × Rendimiento × Calidad. Benchmark mundial: 85% (class-A), 60% (promedio industrial).
        </p>
      </Card>
    </div>
  );
}

// ============================ MAINTENANCE ============================
function MaintPanel({ admin }) {
  const [data, setData] = useState(null);
  const load = () => api.getMaintenance().then(setData);
  useEffect(() => { load(); const id = setInterval(load, 8000); return () => clearInterval(id); }, []);

  const ack = async (component, action) => {
    if (!window.confirm(`¿Registrar ${action} de ${component}?`)) return;
    await api.maintAck(component, action);
    load();
  };

  if (!data) return <div className="p-10 text-slate-500 font-mono">Cargando...</div>;
  const items = data.items || [];

  return (
    <div className="space-y-px">
      <Card className="p-5" testid="maint-info">
        <SectionTitle kicker="01">Mantenimiento predictivo</SectionTitle>
        <p className="text-sm text-slate-400 mt-2">Horas de marcha acumuladas por componente. Cuando se acerca al umbral, sugerimos la próxima intervención.</p>
      </Card>

      <Card className="p-0" testid="maint-table">
        <div className="grid grid-cols-7 gap-2 px-4 py-2 border-b font-mono text-[10px] uppercase tracking-wider text-slate-500" style={{ borderColor: 'var(--border)' }}>
          <span>Componente</span><span>Acción</span><span>h marcha</span><span>Umbral</span><span>Restantes</span><span>Estado</span><span></span>
        </div>
        {items.map((m, i) => {
          const sCls = m.status === 'due' ? 'text-red-400' : m.status === 'warning' ? 'text-amber-300' : 'text-green-400';
          return (
            <div key={`${m.componente}-${m.accion}`} className="grid grid-cols-7 gap-2 items-center px-4 py-2 border-b last:border-b-0 font-mono text-xs" style={{ borderColor: 'var(--border)' }} data-testid={`maint-row-${i}`}>
              <span className="text-slate-200">{m.componente}</span>
              <span className="text-slate-300">{m.accion}</span>
              <span className="text-slate-200">{m.horas_marcha}h</span>
              <span className="text-slate-400">{m.umbral_h}h</span>
              <span className={sCls}>{m.horas_restantes}h</span>
              <span className={sCls}>{m.status.toUpperCase()} · {m.pct}%</span>
              <span>
                {(m.status === 'warning' || m.status === 'due') && (
                  <button onClick={() => ack(m.componente, m.accion)} className="text-amber-300 hover:text-amber-200 text-xs font-mono" data-testid={`maint-ack-${i}`}>Registrar</button>
                )}
              </span>
            </div>
          );
        })}
      </Card>
    </div>
  );
}

// ============================ ENERGY ============================
function EnergyPanel({ admin }) {
  const [data, setData] = useState(null);
  const [prices, setPrices] = useState({});
  const [editing, setEditing] = useState(false);

  const load = () => api.getEnergy().then(d => { setData(d); setPrices(d.prices); });
  useEffect(() => { load(); const id = setInterval(load, 6000); return () => clearInterval(id); }, []);

  const save = async () => {
    await api.setPrices(prices);
    setEditing(false);
    load();
  };

  const doReset = async (what) => {
    if (!window.confirm(`¿Reiniciar contadores de ${what}? No se puede deshacer.`)) return;
    await api.opsReset(what);
    load();
  };

  if (!data) return <div className="p-10 text-slate-500 font-mono">Cargando...</div>;

  return (
    <div className="space-y-px">
      <Card className="p-5" testid="energy-kpis">
        <SectionTitle kicker="01">Energía y costos</SectionTitle>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px hair-grid mt-3">
          <div className="surface p-4" data-testid="energy-kwh"><Metric label="Total kWh" value={data.total_kwh.toFixed(1)} unit="kWh" color="var(--amber)" big /></div>
          <div className="surface p-4" data-testid="energy-gas"><Metric label="Gas natural" value={data.gas_m3.toFixed(1)} unit="m³" color="#FCA5A5" big /></div>
          <div className="surface p-4" data-testid="energy-cost"><Metric label="Costo total" value={`$${(data.energy_cost_ars).toLocaleString('es-AR', { maximumFractionDigits: 0 })}`} unit="ARS" color="#86EFAC" big /></div>
          <div className="surface p-4" data-testid="energy-cost-per-kg"><Metric label="Costo / kg" value={`$${data.cost_per_kg_ars.toFixed(0)}`} unit="ARS" color="#93C5FD" big /></div>
          <div className="surface p-4" data-testid="energy-produced"><Metric label="Producción" value={data.kg_produced.toFixed(0)} unit="kg" color="var(--text)" /></div>
          <div className="surface p-4" data-testid="energy-revenue"><Metric label="Ingresos" value={`$${data.revenue_ars.toLocaleString('es-AR', { maximumFractionDigits: 0 })}`} unit="ARS" color="#86EFAC" /></div>
          <div className="surface p-4" data-testid="energy-margin"><Metric label="Margen / kg" value={`$${data.margin_per_kg_ars.toFixed(0)}`} unit="ARS" color={data.margin_per_kg_ars > 0 ? '#86EFAC' : '#FCA5A5'} /></div>
          <div className="surface p-4" data-testid="energy-runtime-total"><Metric label="Total horas marcha" value={Object.values(data.runtime_hours).reduce((a,b)=>a+b,0).toFixed(1)} unit="h" color="var(--text-2)" /></div>
        </div>
      </Card>

      <Card className="p-5" testid="energy-prices">
        <div className="flex items-center justify-between mb-3">
          <SectionTitle kicker="02">Precios de referencia</SectionTitle>
          {admin && !editing && <Btn testid="prices-edit" variant="secondary" onClick={() => setEditing(true)}>Editar</Btn>}
        </div>
        {!editing ? (
          <div className="grid grid-cols-3 gap-px hair-grid">
            <div className="surface p-4"><Metric label="kWh industrial" value={`$${data.prices.kwh_ars}`} unit="ARS" /></div>
            <div className="surface p-4"><Metric label="m³ gas natural" value={`$${data.prices.m3_gas_ars}`} unit="ARS" /></div>
            <div className="surface p-4"><Metric label="kg yerba venta" value={`$${data.prices.kg_yerba_venta_ars}`} unit="ARS" /></div>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            <NumberInput testid="price-kwh" label="kWh ARS" value={prices.kwh_ars} onChange={(v) => setPrices({ ...prices, kwh_ars: v })} />
            <NumberInput testid="price-gas" label="m³ gas ARS" value={prices.m3_gas_ars} onChange={(v) => setPrices({ ...prices, m3_gas_ars: v })} />
            <NumberInput testid="price-yerba" label="kg yerba venta ARS" value={prices.kg_yerba_venta_ars} onChange={(v) => setPrices({ ...prices, kg_yerba_venta_ars: v })} />
            <div className="col-span-3 flex gap-2">
              <Btn testid="prices-save" onClick={save}>Guardar</Btn>
              <Btn testid="prices-cancel" variant="secondary" onClick={() => { setEditing(false); setPrices(data.prices); }}>Cancelar</Btn>
            </div>
          </div>
        )}
      </Card>

      <Card className="p-0" testid="energy-by-component">
        <CardHeader title="Consumo por componente" subtitle="kWh acumulado y horas de marcha" />
        <div className="grid grid-cols-4 gap-2 px-4 py-2 border-b font-mono text-[10px] uppercase tracking-wider text-slate-500" style={{ borderColor: 'var(--border)' }}>
          <span>Componente</span><span>Horas marcha</span><span>kWh</span><span>$ ARS</span>
        </div>
        {Object.entries(data.kwh_by_component).map(([comp, kwh], i) => (
          <div key={comp} className="grid grid-cols-4 gap-2 px-4 py-1.5 border-b last:border-b-0 font-mono text-xs" style={{ borderColor: 'var(--border)' }} data-testid={`energy-comp-${i}`}>
            <span className="text-slate-200">{comp}</span>
            <span className="text-slate-300">{(data.runtime_hours[comp] || 0).toFixed(1)}h</span>
            <span className="text-amber-300">{kwh.toFixed(2)}</span>
            <span className="text-green-400">${(kwh * data.prices.kwh_ars).toLocaleString('es-AR', { maximumFractionDigits: 0 })}</span>
          </div>
        ))}
      </Card>

      {admin && (
        <Card className="p-5" testid="energy-reset">
          <SectionTitle kicker="·">Reiniciar contadores</SectionTitle>
          <p className="text-xs text-slate-500 font-mono mt-2 mb-3">Útil al iniciar un nuevo ciclo de producción o auditoría.</p>
          <div className="flex gap-2 flex-wrap">
            <Btn testid="reset-energy" variant="secondary" onClick={() => doReset('energy')}>Reset energía</Btn>
            <Btn testid="reset-runtime" variant="secondary" onClick={() => doReset('runtime')}>Reset horas marcha</Btn>
            <Btn testid="reset-production" variant="secondary" onClick={() => doReset('production')}>Reset producción</Btn>
            <Btn testid="reset-all" variant="danger" onClick={() => doReset('all')}>Reset TODO</Btn>
          </div>
        </Card>
      )}
    </div>
  );
}

// ============================ REPORTS ============================
function ReportsPanel() {
  const [batches, setBatches] = useState([]);
  useEffect(() => { api.listBatches().then(setBatches).catch(() => {}); }, []);

  return (
    <div className="space-y-px">
      <Card className="p-5" testid="reports-info">
        <SectionTitle kicker="01">Reportes PDF</SectionTitle>
        <p className="text-sm text-slate-400 mt-2">Generá un reporte ejecutivo mensual o un informe técnico por lote. El PDF se descarga automáticamente.</p>
      </Card>

      <Card className="p-5" testid="report-monthly-card">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-display text-base font-medium text-slate-100">Reporte mensual</h4>
            <p className="text-xs text-slate-500 font-mono mt-1">Incluye OEE, lotes, alarmas, energía y mantenimiento del período actual.</p>
          </div>
          <a href={api.reportMonthlyUrl()} target="_blank" rel="noreferrer" data-testid="report-monthly-download">
            <Btn variant="ai"><span className="inline-flex items-center gap-1"><FileArrowDown size={13}/> Descargar</span></Btn>
          </a>
        </div>
      </Card>

      <Card className="p-0" testid="reports-batches">
        <CardHeader title="Reportes por lote" subtitle="Generá un PDF técnico de cada lote producido" />
        {batches.length === 0 ? (
          <div className="p-5 font-mono text-xs text-slate-500">Sin lotes registrados. Iniciá uno desde la tab Lotes.</div>
        ) : (
          <div>
            {batches.slice(0, 50).map((b, i) => (
              <div key={b.id} className="flex items-center justify-between px-4 py-2.5 border-b last:border-b-0 font-mono text-xs" style={{ borderColor: 'var(--border)' }} data-testid={`report-batch-${i}`}>
                <div className="flex-1">
                  <span className="text-slate-200">{b.id}</span>
                  <span className="text-slate-500 ml-3">{b.receta_nombre || '—'}</span>
                  <span className={`ml-3 ${b.status === 'finished' ? 'text-green-400' : b.status === 'running' ? 'text-amber-300' : 'text-slate-500'}`}>{b.status}</span>
                </div>
                <a href={api.reportBatchUrl(b.id)} target="_blank" rel="noreferrer" data-testid={`report-batch-dl-${b.id}`}>
                  <Btn variant="secondary"><span className="inline-flex items-center gap-1"><FilePdf size={12}/> PDF</span></Btn>
                </a>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

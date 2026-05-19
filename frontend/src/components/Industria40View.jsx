import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Btn, NumberInput, TextInput, Toggle, SectionTitle, StatusBadge } from './UI';
import { api } from '../lib/api';
import { useAuth, isAdmin } from '../lib/auth';
import { Plugs, Broadcast, Cpu, FileArrowUp, ShieldCheck, Lightning, ArrowsLeftRight, Warning } from '@phosphor-icons/react';

export default function Industria40View() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [ext, setExt] = useState(null);
  const [drift, setDrift] = useState({});
  const [audit, setAudit] = useState([]);
  const [tab, setTab] = useState('sources');
  const [calibCsv, setCalibCsv] = useState('');
  const [calibResult, setCalibResult] = useState(null);
  const [calibBusy, setCalibBusy] = useState(false);

  const refresh = async () => {
    try {
      const e = await api.externalStatus();
      setExt(e);
      setDrift(e.drift || {});
    } catch (err) { /* ignore */ }
  };

  const refreshAudit = async () => {
    try { setAudit(await api.auditLog(100)); } catch (err) { /* ignore */ }
  };

  useEffect(() => {
    refresh();
    refreshAudit();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-px">
      {/* Tabs internos */}
      <Card className="p-0" testid="i40-tabs">
        <div className="flex flex-wrap border-b" style={{ borderColor: 'var(--border)' }}>
          {[
            ['sources', 'Fuentes externas', Plugs],
            ['drift', 'Drift sim vs PLC', ArrowsLeftRight],
            ['calib', 'Calibración por CSV', FileArrowUp],
            ['audit', 'Audit log', ShieldCheck],
          ].map(([k, l, Ic]) => (
            <button key={k} data-testid={`i40-tab-${k}`} onClick={() => setTab(k)}
              className={`px-4 py-2.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 ${tab === k ? 'border-amber-300 text-slate-100' : 'border-transparent text-slate-400 hover:text-slate-200'}`}>
              <Ic size={13}/> {l}
            </button>
          ))}
        </div>
      </Card>

      {tab === 'sources' && ext && (
        <SourcesPanel ext={ext} admin={admin} onSaved={refresh} />
      )}

      {tab === 'drift' && (
        <DriftPanel drift={drift} mirror={ext?.mirror} />
      )}

      {tab === 'calib' && (
        <CalibPanel
          admin={admin}
          csv={calibCsv} setCsv={setCalibCsv}
          result={calibResult} setResult={setCalibResult}
          busy={calibBusy} setBusy={setCalibBusy}
        />
      )}

      {tab === 'audit' && (
        <AuditPanel rows={audit} onRefresh={refreshAudit} admin={admin} />
      )}
    </div>
  );
}

function SourcesPanel({ ext, admin, onSaved }) {
  const config = ext.config || {};
  return (
    <div className="space-y-px">
      <Card className="p-5" testid="src-info">
        <SectionTitle kicker="01">Fuentes externas (modo Gemelo / Shadow)</SectionTitle>
        <p className="text-sm text-slate-400 mt-2">
          Configurá las conexiones a tu PLC/SCADA real. En modo <span className="text-amber-300 font-mono">twin</span> los valores leídos
          reemplazan al simulador; en modo <span className="text-amber-300 font-mono">shadow</span> el simulador y el PLC corren en
          paralelo y se compara la <span className="text-amber-300">deriva</span>.
        </p>
        <p className="text-xs text-slate-500 font-mono mt-2">Tip: para probar sin un PLC real, dejá host=<span className="text-amber-300">127.0.0.1</span> y port=<span className="text-amber-300">5020</span> — se conectará a tu propio servidor Modbus en loopback.</p>
      </Card>

      <ModbusClientCard config={config.modbus_client || {}} status={ext.modbus_client} admin={admin} onSaved={onSaved} />
      <OpcUaClientCard config={config.opcua_client || {}} status={ext.opcua_client} admin={admin} onSaved={onSaved} />
      <MqttSubscriberCard config={config.mqtt_subscriber || {}} status={ext.mqtt_subscriber} admin={admin} onSaved={onSaved} />

      <Card className="p-5" testid="mirror-card">
        <div className="flex items-center justify-between mb-2">
          <SectionTitle kicker="·">Valores leídos en vivo</SectionTitle>
          <span className="font-mono text-[10px] text-slate-500">{Object.keys(ext.mirror?.values || {}).length} tags</span>
        </div>
        {Object.keys(ext.mirror?.values || {}).length === 0 ? (
          <p className="text-xs text-slate-500 font-mono">Sin lecturas. Habilitá al menos una fuente.</p>
        ) : (
          <div className="border" style={{ borderColor: 'var(--border)' }}>
            <div className="grid grid-cols-4 gap-2 px-3 py-2 border-b font-mono text-[10px] uppercase tracking-wider text-slate-500" style={{ borderColor: 'var(--border)' }}>
              <span>Tag</span><span>Valor</span><span>Fuente</span><span>Actualizado</span>
            </div>
            {Object.entries(ext.mirror.values).map(([tag, val]) => (
              <div key={tag} className="grid grid-cols-4 gap-2 px-3 py-1.5 border-b last:border-b-0 font-mono text-xs" style={{ borderColor: 'var(--border)' }} data-testid={`mirror-row-${tag}`}>
                <span className="text-slate-200 truncate">{tag}</span>
                <span className="text-amber-300">{typeof val === 'number' ? val.toFixed(2) : val}</span>
                <span className="text-slate-400">{ext.mirror.sources?.[tag] || '–'}</span>
                <span className="text-slate-500">{ext.mirror.last_update?.[tag] ? new Date(ext.mirror.last_update[tag]).toLocaleTimeString() : '–'}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function ModbusClientCard({ config, status, admin, onSaved }) {
  const [enabled, setEnabled] = useState(!!config.enabled);
  const [host, setHost] = useState(config.host || '127.0.0.1');
  const [port, setPort] = useState(config.port || 5020);
  const [interval, setInterval] = useState(config.interval || 2.0);

  useEffect(() => {
    setEnabled(!!config.enabled);
    setHost(config.host || '127.0.0.1');
    setPort(config.port || 5020);
    setInterval(config.interval || 2.0);
  }, [config.enabled, config.host, config.port, config.interval]);

  const save = async () => {
    await api.configureExternal('modbus_client', { enabled, host, port, interval });
    onSaved && onSaved();
  };

  return (
    <Card className="p-5" testid="modbus-client-card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Cpu size={16} className="text-blue-300"/>
          <h4 className="font-display text-base font-medium text-slate-100">Cliente Modbus TCP</h4>
        </div>
        <StatusBadge state={status?.running ? 'online' : 'offline'} label={status?.running ? 'POLLING' : 'OFF'} testid="modbus-client-badge" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <TextInput testid="mb-cli-host" label="Host PLC" value={host} onChange={setHost} />
        <NumberInput testid="mb-cli-port" label="Puerto" value={port} onChange={setPort} />
        <NumberInput testid="mb-cli-interval" label="Intervalo" unit="s" value={interval} onChange={setInterval} step={0.5} />
        <div className="flex items-end justify-between">
          <Toggle testid="mb-cli-enabled" value={enabled} onChange={setEnabled} label={enabled ? 'Habilitado' : 'Pausado'} />
        </div>
      </div>
      {status?.error && <p className="text-xs text-red-400 font-mono mt-2">⚠ {status.error}</p>}
      <div className="mt-3 flex gap-2 items-center">
        <Btn testid="mb-cli-save" onClick={save} disabled={!admin}>Aplicar</Btn>
        {!admin && <span className="text-xs text-slate-500 font-mono">solo admin puede modificar</span>}
      </div>
    </Card>
  );
}

function OpcUaClientCard({ config, status, admin, onSaved }) {
  const [enabled, setEnabled] = useState(!!config.enabled);
  const [endpoint, setEndpoint] = useState(config.endpoint || 'opc.tcp://127.0.0.1:4840/yerba/');
  const [interval, setInterval] = useState(config.interval || 2.0);

  useEffect(() => {
    setEnabled(!!config.enabled);
    setEndpoint(config.endpoint || 'opc.tcp://127.0.0.1:4840/yerba/');
    setInterval(config.interval || 2.0);
  }, [config.enabled, config.endpoint, config.interval]);

  const save = async () => {
    await api.configureExternal('opcua_client', { enabled, endpoint, interval });
    onSaved && onSaved();
  };

  return (
    <Card className="p-5" testid="opcua-client-card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2"><Cpu size={16} className="text-green-300"/><h4 className="font-display text-base font-medium text-slate-100">Cliente OPC UA</h4></div>
        <StatusBadge state={status?.running ? 'online' : 'offline'} label={status?.running ? 'POLLING' : 'OFF'} testid="opcua-client-badge" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <TextInput testid="op-cli-endpoint" label="Endpoint" value={endpoint} onChange={setEndpoint} className="md:col-span-2" />
        <NumberInput testid="op-cli-interval" label="Intervalo" unit="s" value={interval} onChange={setInterval} step={0.5} />
      </div>
      <div className="mt-2 flex items-center justify-between">
        <Toggle testid="op-cli-enabled" value={enabled} onChange={setEnabled} label={enabled ? 'Habilitado' : 'Pausado'} />
        <Btn testid="op-cli-save" onClick={save} disabled={!admin}>Aplicar</Btn>
      </div>
      {status?.error && <p className="text-xs text-red-400 font-mono mt-2">⚠ {status.error}</p>}
    </Card>
  );
}

function MqttSubscriberCard({ config, status, admin, onSaved }) {
  const [enabled, setEnabled] = useState(!!config.enabled);
  const [broker, setBroker] = useState(config.broker || 'localhost');
  const [port, setPort] = useState(config.port || 1883);
  const [topicBase, setTopicBase] = useState(config.topic_base || 'yerba_in');
  const [usr, setUsr] = useState(config.user || '');
  const [pwd, setPwd] = useState(config.pass || '');

  useEffect(() => {
    setEnabled(!!config.enabled);
    setBroker(config.broker || 'localhost');
    setPort(config.port || 1883);
    setTopicBase(config.topic_base || 'yerba_in');
    setUsr(config.user || '');
    setPwd(config.pass || '');
  }, [config.enabled, config.broker, config.port, config.topic_base, config.user, config.pass]);

  const save = async () => {
    await api.configureExternal('mqtt_subscriber', { enabled, broker, port, topic_base: topicBase, user: usr, password: pwd });
    onSaved && onSaved();
  };

  return (
    <Card className="p-5" testid="mqtt-sub-card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2"><Broadcast size={16} className="text-purple-200"/><h4 className="font-display text-base font-medium text-slate-100">Suscriptor MQTT</h4></div>
        <StatusBadge state={status?.running ? 'online' : 'offline'} label={status?.running ? 'SUBSCRIBED' : 'OFF'} testid="mqtt-sub-badge" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <TextInput testid="mq-broker" label="Broker" value={broker} onChange={setBroker} />
        <NumberInput testid="mq-port" label="Puerto" value={port} onChange={setPort} />
        <TextInput testid="mq-topic" label="Topic base" value={topicBase} onChange={setTopicBase} />
        <div className="flex items-end justify-between">
          <Toggle testid="mq-enabled" value={enabled} onChange={setEnabled} label={enabled ? 'Habilitado' : 'Pausado'} />
        </div>
        <TextInput testid="mq-user" label="Usuario" value={usr} onChange={setUsr} />
        <TextInput testid="mq-pass" label="Contraseña" value={pwd} onChange={setPwd} />
      </div>
      {status?.error && <p className="text-xs text-red-400 font-mono mt-2">⚠ {status.error}</p>}
      <div className="mt-3">
        <Btn testid="mq-save" onClick={save} disabled={!admin}>Aplicar</Btn>
      </div>
      <p className="text-xs text-slate-500 font-mono mt-3">Topics esperados: <span className="text-amber-300">{topicBase}/zapecado/temperatura</span>, <span className="text-amber-300">{topicBase}/secado/humedad</span>, etc. Payload: número o JSON con campo "value".</p>
    </Card>
  );
}

function DriftPanel({ drift, mirror }) {
  const entries = Object.entries(drift || {});
  return (
    <div className="space-y-px">
      <Card className="p-5" testid="drift-info">
        <SectionTitle kicker="01">Deriva: Simulación vs. Fuente externa</SectionTitle>
        <p className="text-sm text-slate-400 mt-2">Comparación tag-a-tag entre lo que el simulador predice y lo que mide tu PLC. Activá el modo <span className="text-amber-300 font-mono">shadow</span> para ver datos en vivo.</p>
      </Card>

      <Card className="p-0" testid="drift-table">
        {entries.length === 0 ? (
          <div className="p-5 font-mono text-xs text-slate-500">Sin lecturas todavía. Habilitá una fuente externa y poné el modo en shadow o twin.</div>
        ) : (
          <div className="overflow-x-auto">
            <div className="grid grid-cols-5 gap-2 px-4 py-2 border-b font-mono text-[10px] uppercase tracking-wider text-slate-500" style={{ borderColor: 'var(--border)' }}>
              <span>Tag</span><span>Simulación</span><span>Externo</span><span>Δ (sim-ext)</span><span>% error</span>
            </div>
            {entries.map(([tag, v], i) => {
              const driftColor = v.pct > 10 ? 'text-red-400' : v.pct > 3 ? 'text-amber-400' : 'text-green-400';
              return (
                <div key={tag} className="grid grid-cols-5 gap-2 px-4 py-2 border-b last:border-b-0 font-mono text-sm" style={{ borderColor: 'var(--border)' }} data-testid={`drift-row-${i}`}>
                  <span className="text-slate-200">{tag}</span>
                  <span className="text-slate-300">{v.sim.toFixed(2)}</span>
                  <span className="text-amber-300">{v.ext.toFixed(2)}</span>
                  <span className={driftColor}>{v.delta > 0 ? '+' : ''}{v.delta.toFixed(2)}</span>
                  <span className={driftColor}>{v.pct.toFixed(2)}%</span>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

function CalibPanel({ admin, csv, setCsv, result, setResult, busy, setBusy }) {
  const onUpload = async (file) => {
    if (!file) return;
    const text = await file.text();
    setCsv(text);
  };

  const analyze = async () => {
    if (!csv.trim()) { alert('Falta CSV'); return; }
    setBusy(true);
    try {
      const r = await api.calibrationAnalyze(csv);
      setResult(r);
    } catch (e) {
      alert(e?.response?.data?.detail || 'Error');
    }
    setBusy(false);
  };

  const apply = async () => {
    if (!result) return;
    if (!window.confirm('¿Aplicar τ propuestos al simulador?')) return;
    await api.calibrationApply(result);
    alert('Aplicado. Verás cambios en la dinámica de las variables.');
  };

  return (
    <div className="space-y-px">
      <Card className="p-5" testid="calib-info">
        <SectionTitle kicker="01">Calibración por CSV histórico</SectionTitle>
        <p className="text-sm text-slate-400 mt-2">Subí un CSV de tu planta real (idealmente exportado de este mismo gemelo o de tu SCADA). El sistema ajusta las constantes de tiempo (τ) y el ruido por mínimos cuadrados para que el simulador se parezca al comportamiento real.</p>
        <p className="text-xs text-slate-500 font-mono mt-2">Columnas esperadas: <span className="text-amber-300">zap_temperatura</span>, <span className="text-amber-300">sec_temperatura</span>, <span className="text-amber-300">sec_humedad</span>, <span className="text-amber-300">cam1_temperatura</span></p>
      </Card>

      <Card className="p-5" testid="calib-upload">
        <SectionTitle kicker="02">Cargar CSV</SectionTitle>
        <div className="mt-3 space-y-3">
          <input
            data-testid="calib-file"
            type="file"
            accept=".csv,text/csv"
            disabled={!admin}
            onChange={(e) => onUpload(e.target.files?.[0])}
            className="block w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-4 file:border-0 file:text-xs file:font-medium file:bg-amber-300/15 file:text-amber-300 hover:file:bg-amber-300/25 file:cursor-pointer"
          />
          <textarea
            data-testid="calib-csv-input"
            value={csv}
            onChange={(e) => setCsv(e.target.value)}
            placeholder="O pegá el contenido del CSV acá..."
            className="field w-full h-32 font-mono text-xs"
          />
          <div className="flex gap-2">
            <Btn testid="calib-analyze" onClick={analyze} disabled={busy || !csv.trim() || !admin}><span className="inline-flex items-center gap-1"><Lightning size={13}/> {busy ? 'Analizando...' : 'Analizar'}</span></Btn>
            {result && <Btn testid="calib-apply" variant="ai" onClick={apply} disabled={!admin}>Aplicar al simulador</Btn>}
          </div>
        </div>
      </Card>

      {result && (
        <Card className="p-5" testid="calib-result">
          <SectionTitle kicker="03">Resultado del análisis</SectionTitle>
          <p className="text-xs text-slate-500 font-mono mt-1">{result.rows} filas · columnas: {(result.columns || []).join(', ')}</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
            {['zapecado', 'secado_humedad', 'camara1'].map(k => result[k] && (
              <div key={k} className="border p-3" style={{ borderColor: 'var(--border)' }}>
                <h5 className="font-mono text-[10px] uppercase tracking-wider text-slate-500 mb-2">{k.replace('_', ' ')}</h5>
                <div className="space-y-1 font-mono text-xs">
                  <div className="flex justify-between"><span className="text-slate-400">τ propuesto:</span><span className="text-amber-300">{result[k].tau}s</span></div>
                  <div className="flex justify-between"><span className="text-slate-400">Ruido σ:</span><span className="text-slate-200">{result[k].noise_std}</span></div>
                  <div className="flex justify-between"><span className="text-slate-400">Muestras:</span><span className="text-slate-200">{result[k].samples}</span></div>
                  {result[k].target_inferido && <div className="flex justify-between"><span className="text-slate-400">Target:</span><span className="text-slate-200">{result[k].target_inferido}</span></div>}
                  {result[k].piso_inferido && <div className="flex justify-between"><span className="text-slate-400">Piso:</span><span className="text-slate-200">{result[k].piso_inferido}</span></div>}
                  {result[k].setpoint_inferido && <div className="flex justify-between"><span className="text-slate-400">Setpoint:</span><span className="text-slate-200">{result[k].setpoint_inferido}</span></div>}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function AuditPanel({ rows, onRefresh, admin }) {
  return (
    <div className="space-y-px">
      <Card className="p-5" testid="audit-info">
        <div className="flex items-center justify-between">
          <SectionTitle kicker="01">Audit Log {admin ? '(global)' : '(mis acciones)'}</SectionTitle>
          <Btn testid="audit-refresh" variant="secondary" onClick={onRefresh}>Refrescar</Btn>
        </div>
        <p className="text-sm text-slate-400 mt-2">Toda acción de configuración queda registrada con fecha, usuario, IP y detalle.</p>
      </Card>

      <Card className="p-0" testid="audit-table">
        {rows.length === 0 ? (
          <div className="p-5 font-mono text-xs text-slate-500">Sin eventos todavía.</div>
        ) : (
          <div className="overflow-x-auto">
            <div className="grid grid-cols-5 gap-2 px-4 py-2 border-b font-mono text-[10px] uppercase tracking-wider text-slate-500" style={{ borderColor: 'var(--border)' }}>
              <span>Fecha</span><span>Usuario</span><span>Acción</span><span>Detalle</span><span>IP</span>
            </div>
            {rows.map((r, i) => (
              <div key={i} className="grid grid-cols-5 gap-2 px-4 py-2 border-b last:border-b-0 font-mono text-xs" style={{ borderColor: 'var(--border)' }} data-testid={`audit-row-${i}`}>
                <span className="text-slate-400">{new Date(r.ts).toLocaleString()}</span>
                <span className="text-amber-300">{r.username}</span>
                <span className="text-slate-200">{r.action}</span>
                <span className="text-slate-400 truncate" title={JSON.stringify(r.details)}>{JSON.stringify(r.details).slice(0, 60)}</span>
                <span className="text-slate-500">{r.ip || '–'}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

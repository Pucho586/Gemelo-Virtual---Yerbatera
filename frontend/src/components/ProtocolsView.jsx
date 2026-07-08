import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Btn, NumberInput, TextInput, Toggle, SectionTitle, StatusBadge } from './UI';
import { api } from '../lib/api';
import { useAuth, isAdmin } from '../lib/auth';
import { Cpu, Broadcast, Plugs, FloppyDisk, Table, Info } from '@phosphor-icons/react';

/*
 * Pestaña unificada de PROTOCOLOS.
 * - Elegí qué protocolo(s) usar (no se usan todos a la vez).
 * - Configurá la conexión de cada uno.
 * - Mirá qué variables expone cada protocolo y en qué dirección/topic/nodo.
 */
const META = {
  modbus: { label: 'Modbus TCP', Icon: Cpu, color: 'text-blue-300', desc: 'PLCs clásicos. Cada variable en un registro (unit / addr).' },
  mqtt: { label: 'MQTT', Icon: Broadcast, color: 'text-purple-200', desc: 'Publica cada variable en un topic. Ideal para IoT y Node-RED.' },
  opcua: { label: 'OPC UA', Icon: Plugs, color: 'text-green-300', desc: 'SCADA empresarial. Cada variable es un nodo Objeto.Variable.' },
};

export default function ProtocolsView() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState('');

  const refresh = () => api.getProtocols().then(setData).catch(() => {});
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  if (!data) return <div className="p-10 text-slate-500 font-mono">Cargando protocolos...</div>;

  const toggle = async (name, enabled) => {
    if (!admin) return;
    try {
      const r = await api.setProtocolEnabled(name, enabled);
      setMsg(enabled
        ? (r.hot_started ? `${META[name].label} activado ✓` : `${META[name].label}: activado (arranca al reiniciar)`)
        : `${META[name].label}: ${r.note || 'desactivado'}`);
      setTimeout(() => setMsg(''), 4000);
      refresh();
    } catch (e) {
      setMsg(e?.response?.data?.detail || 'Error');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 px-5 py-4 border rounded-lg" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }} data-testid="protocols-intro">
        <Info size={20} className="text-amber-300 shrink-0 mt-0.5" weight="duotone" />
        <div>
          <div className="text-sm font-medium text-slate-200">Elegí con qué protocolo se maneja el gemelo</div>
          <p className="text-[13px] text-slate-400 mt-1 leading-relaxed">
            No hace falta usar los tres a la vez. Activá solo el que necesites para cada ocasión.
            Las mismas variables se exponen en el protocolo elegido con el direccionamiento que ves abajo.
            Para <b className="text-slate-300">leer</b> de un PLC real (modo Shadow/Gemelo), usá la pestaña <b className="text-slate-300">Industria 4.0</b>.
          </p>
        </div>
      </div>

      {['modbus', 'mqtt', 'opcua'].map((name) => (
        <ProtocolCard key={name} name={name} block={data[name]} admin={admin} onToggle={toggle} onSaved={refresh} />
      ))}

      <VariablesTable variables={data.variables} enabled={{ modbus: data.modbus.enabled, mqtt: data.mqtt.enabled, opcua: data.opcua.enabled }} />

      {msg && <div className="surface p-4 font-mono text-xs text-amber-300" data-testid="protocols-msg">{msg}</div>}
    </div>
  );
}

function stateOf(block) {
  if (!block.enabled) return { s: 'offline', label: 'DESACTIVADO' };
  if (block.error) return { s: 'offline', label: 'ERROR' };
  if (block.running) return { s: 'online', label: 'ACTIVO' };
  return { s: 'warning', label: 'AL REINICIAR' };
}

function ProtocolCard({ name, block, admin, onToggle, onSaved }) {
  const m = META[name];
  const st = stateOf(block);
  return (
    <Card className="p-5" testid={`proto-${name}`}>
      <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
        <div className="flex items-center gap-2.5">
          <m.Icon size={20} className={m.color} weight="duotone" />
          <div>
            <h3 className="font-display text-base font-medium text-slate-100">{m.label}</h3>
            <p className="text-[11px] text-slate-500">{m.desc}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge state={st.s} label={st.label} testid={`proto-${name}-badge`} />
          <Toggle testid={`proto-${name}-toggle`} value={block.enabled} onChange={(v) => onToggle(name, v)} label={block.enabled ? 'Usar' : 'Apagado'} />
        </div>
      </div>
      {block.error && <p className="text-xs text-red-400 font-mono mb-3">⚠ {block.error}</p>}
      <ProtocolParams name={name} config={block.config} admin={admin} onSaved={onSaved} />
    </Card>
  );
}

function ProtocolParams({ name, config, admin, onSaved }) {
  const [cfg, setCfg] = useState(config);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setCfg(config); }, [config]);
  const up = (k, v) => setCfg((p) => ({ ...p, [k]: v }));

  const save = async () => {
    setSaving(true);
    try { await api.patchConfig({ [name]: cfg }); onSaved && onSaved(); }
    finally { setSaving(false); }
  };

  const fields = {
    modbus: (
      <>
        <TextInput testid="p-mb-ip" label="IP" value={cfg.ip} onChange={(v) => up('ip', v)} />
        <NumberInput testid="p-mb-port" label="Puerto" value={cfg.port} onChange={(v) => up('port', v)} />
        <NumberInput testid="p-mb-rate" label="Refresh" unit="s" value={cfg.rate} onChange={(v) => up('rate', v)} step={0.5} />
      </>
    ),
    mqtt: (
      <>
        <TextInput testid="p-mq-broker" label="Broker" value={cfg.broker} onChange={(v) => up('broker', v)} />
        <NumberInput testid="p-mq-port" label="Puerto" value={cfg.port} onChange={(v) => up('port', v)} />
        <TextInput testid="p-mq-topic" label="Topic base" value={cfg.topic} onChange={(v) => up('topic', v)} />
        <NumberInput testid="p-mq-interval" label="Intervalo" unit="s" value={cfg.interval} onChange={(v) => up('interval', v)} />
        <TextInput testid="p-mq-user" label="Usuario" value={cfg.user} onChange={(v) => up('user', v)} />
        <TextInput testid="p-mq-pass" label="Contraseña" value={cfg.pass} onChange={(v) => up('pass', v)} />
      </>
    ),
    opcua: (
      <>
        <TextInput testid="p-op-host" label="Host" value={cfg.host} onChange={(v) => up('host', v)} />
        <NumberInput testid="p-op-port" label="Puerto" value={cfg.port} onChange={(v) => up('port', v)} />
        <TextInput testid="p-op-path" label="Path" value={cfg.path} onChange={(v) => up('path', v)} />
        <TextInput testid="p-op-ns" label="Namespace" value={cfg.namespace} onChange={(v) => up('namespace', v)} />
      </>
    ),
  };

  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">{fields[name]}</div>
      <div className="mt-3 flex items-center gap-2">
        <Btn testid={`p-${name}-save`} onClick={save} disabled={!admin || saving}>
          <span className="inline-flex items-center gap-1"><FloppyDisk size={13} /> {saving ? 'Guardando...' : 'Guardar conexión'}</span>
        </Btn>
        {!admin && <span className="text-xs text-slate-500 font-mono">solo admin</span>}
      </div>
    </div>
  );
}

function VariablesTable({ variables, enabled }) {
  const [q, setQ] = useState('');
  const rows = (variables || []).filter((v) => v.label.toLowerCase().includes(q.toLowerCase()) || v.tag.includes(q.toLowerCase()));
  const head = (label, on) => (
    <span className={on ? 'text-slate-200' : 'text-slate-600 line-through'}>{label}</span>
  );
  return (
    <Card className="p-0" testid="proto-variables">
      <CardHeader
        title="Variables expuestas"
        subtitle="La misma variable, direccionada en cada protocolo. Los apagados aparecen tachados."
        action={<input data-testid="proto-var-search" className="field text-xs" placeholder="Buscar variable..." value={q} onChange={(e) => setQ(e.target.value)} />}
      />
      <div className="overflow-x-auto">
        <div className="min-w-[640px]">
          <div className="grid grid-cols-[1.6fr_1.1fr_1.3fr_1.6fr] gap-2 px-4 py-2 border-b font-mono text-[10px] uppercase tracking-wider text-slate-500" style={{ borderColor: 'var(--border)' }}>
            <span className="inline-flex items-center gap-1"><Table size={11} /> Variable</span>
            {head('Modbus (unit/reg)', enabled.modbus)}
            {head('OPC UA (nodo)', enabled.opcua)}
            {head('MQTT (topic)', enabled.mqtt)}
          </div>
          {rows.map((v) => (
            <div key={v.tag} className="grid grid-cols-[1.6fr_1.1fr_1.3fr_1.6fr] gap-2 px-4 py-2 border-b last:border-b-0 font-mono text-xs items-center" style={{ borderColor: 'var(--border)' }} data-testid={`proto-var-${v.tag}`}>
              <span className="text-slate-200">{v.label}{v.unit && <span className="text-slate-500"> ({v.unit})</span>}</span>
              <span className={enabled.modbus ? 'text-blue-300' : 'text-slate-600'}>u{v.modbus.unit} / r{v.modbus.addr} <span className="text-slate-600">×{v.modbus.scale}</span></span>
              <span className={enabled.opcua ? 'text-green-300' : 'text-slate-600'}>{v.opcua}</span>
              <span className={enabled.mqtt ? 'text-purple-200' : 'text-slate-600'}>{v.mqtt}</span>
            </div>
          ))}
          {rows.length === 0 && <div className="px-4 py-6 text-center font-mono text-xs text-slate-500">Sin resultados para "{q}"</div>}
        </div>
      </div>
    </Card>
  );
}

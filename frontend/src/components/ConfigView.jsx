import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Btn, NumberInput, TextInput, Toggle, StatusBadge, SectionTitle } from './UI';
import { api } from '../lib/api';
import { Cloud, MapPin, FloppyDisk, Download, MagnifyingGlass } from '@phosphor-icons/react';

export default function ConfigView({ status }) {
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [files, setFiles] = useState([]);
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [savedMsg, setSavedMsg] = useState('');

  useEffect(() => {
    api.getConfig().then(setCfg);
    api.listDataFiles().then(setFiles);
  }, []);

  if (!cfg) return <div className="p-10 text-slate-500 font-mono">Cargando configuración...</div>;

  const update = (section, key, value) => {
    setCfg(prev => ({ ...prev, [section]: { ...prev[section], [key]: value } }));
  };

  const updateRoot = (key, value) => {
    setCfg(prev => ({ ...prev, [key]: value }));
  };

  const save = async () => {
    setSaving(true);
    try {
      const patch = {
        modbus: cfg.modbus,
        mqtt: cfg.mqtt,
        opcua: cfg.opcua,
        simulacion: cfg.simulacion,
        persistence: cfg.persistence,
        limits: cfg.limits,
      };
      await api.patchConfig(patch);
      setSavedMsg('Guardado en config_yerba.yaml ✓');
      setTimeout(() => setSavedMsg(''), 3500);
    } catch (e) {
      setSavedMsg(`Error: ${e?.message}`);
    } finally {
      setSaving(false);
    }
  };

  const doSearch = async () => {
    if (!search.trim()) return;
    setSearching(true);
    try {
      const res = await api.searchWeather(search.trim());
      setSearchResults(res);
    } finally {
      setSearching(false);
    }
  };

  const setLocation = async (r) => {
    await api.setWeatherLocation({ latitude: r.latitude, longitude: r.longitude, city: r.label });
    const next = await api.getConfig();
    setCfg(next);
    setSearchResults([]);
    setSearch('');
  };

  return (
    <div className="space-y-px">
      {/* Estado de servidores */}
      <Card className="p-5" testid="config-services">
        <SectionTitle kicker="01">Estado de servidores industriales</SectionTitle>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-3 text-xs font-mono">
          <ServiceCell label="Modbus TCP" s={status?.modbus} format={(v) => `${v.ip}:${v.port}`} testid="srv-modbus" />
          <ServiceCell label="MQTT" s={status?.mqtt} format={(v) => `${v.broker}:${v.port}`} testid="srv-mqtt" />
          <ServiceCell label="OPC UA" s={status?.opcua} format={(v) => v.endpoint || '–'} testid="srv-opcua" />
          <ServiceCell label="Clima" s={status?.weather} format={(v) => v.city || '–'} testid="srv-weather" />
          <ServiceCell label="Persistencia CSV" s={status?.persistence} format={(v) => `cada ${v.interval}s`} testid="srv-persist" />
        </div>
      </Card>

      {/* Clima */}
      <Card className="p-5" testid="config-weather">
        <SectionTitle kicker="02">Clima ambiente (Open-Meteo)</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-3">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-slate-300"><MapPin size={14} className="text-amber-300"/> Ubicación actual</div>
            <p className="font-mono text-sm text-slate-100">{cfg.weather?.city || 'Sin ciudad'}</p>
            <p className="font-mono text-xs text-slate-500">{cfg.weather?.latitude?.toFixed(4)}, {cfg.weather?.longitude?.toFixed(4)}</p>
          </div>
          <div className="md:col-span-2 space-y-2">
            <div className="flex gap-2">
              <input
                data-testid="weather-search-input"
                className="field flex-1"
                placeholder="Buscar ciudad (ej: Oberá, Mendoza, São Paulo)..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && doSearch()}
              />
              <Btn testid="weather-search-btn" variant="secondary" onClick={doSearch} disabled={searching}><span className="inline-flex items-center gap-1"><MagnifyingGlass size={12}/> Buscar</span></Btn>
            </div>
            {searchResults.length > 0 && (
              <div className="border" style={{ borderColor: 'var(--border)' }}>
                {searchResults.map((r, i) => (
                  <button key={i} data-testid={`weather-result-${i}`} onClick={() => setLocation(r)} className="block w-full text-left px-3 py-2 text-xs font-mono text-slate-300 hover:bg-[#1A1E1C] border-b last:border-b-0" style={{ borderColor: 'var(--border)' }}>
                    <span className="text-slate-100">{r.label}</span> <span className="text-slate-500">· {r.latitude.toFixed(2)}, {r.longitude.toFixed(2)}</span>
                  </button>
                ))}
              </div>
            )}
            <p className="text-xs text-slate-500 font-mono">El clima se refresca cada {cfg.weather?.interval_seconds || 600}s y se inyecta en zapecado/secado/cámaras.</p>
          </div>
        </div>
      </Card>

      {/* Modbus */}
      <Card className="p-5" testid="config-modbus">
        <SectionTitle kicker="03">Modbus TCP</SectionTitle>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-3">
          <TextInput testid="modbus-ip" label="IP" value={cfg.modbus.ip} onChange={(v) => update('modbus', 'ip', v)} />
          <NumberInput testid="modbus-port" label="Puerto" value={cfg.modbus.port} onChange={(v) => update('modbus', 'port', v)} />
          <NumberInput testid="modbus-rate" label="Refresh" unit="s" value={cfg.modbus.rate} onChange={(v) => update('modbus', 'rate', v)} step={0.5} />
        </div>
      </Card>

      {/* MQTT */}
      <Card className="p-5" testid="config-mqtt">
        <SectionTitle kicker="04">MQTT</SectionTitle>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3">
          <TextInput testid="mqtt-broker" label="Broker" value={cfg.mqtt.broker} onChange={(v) => update('mqtt', 'broker', v)} />
          <NumberInput testid="mqtt-port" label="Puerto" value={cfg.mqtt.port} onChange={(v) => update('mqtt', 'port', v)} />
          <TextInput testid="mqtt-topic" label="Topic base" value={cfg.mqtt.topic} onChange={(v) => update('mqtt', 'topic', v)} />
          <NumberInput testid="mqtt-interval" label="Intervalo" unit="s" value={cfg.mqtt.interval} onChange={(v) => update('mqtt', 'interval', v)} />
          <TextInput testid="mqtt-user" label="Usuario" value={cfg.mqtt.user} onChange={(v) => update('mqtt', 'user', v)} />
          <TextInput testid="mqtt-pass" label="Contraseña" value={cfg.mqtt.pass} onChange={(v) => update('mqtt', 'pass', v)} />
          <NumberInput testid="mqtt-keepalive" label="Keepalive" unit="s" value={cfg.mqtt.keepalive} onChange={(v) => update('mqtt', 'keepalive', v)} />
        </div>
      </Card>

      {/* OPC UA */}
      <Card className="p-5" testid="config-opcua">
        <SectionTitle kicker="05">OPC UA</SectionTitle>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-3">
          <TextInput testid="opcua-host" label="Host" value={cfg.opcua.host} onChange={(v) => update('opcua', 'host', v)} />
          <NumberInput testid="opcua-port" label="Puerto" value={cfg.opcua.port} onChange={(v) => update('opcua', 'port', v)} />
          <TextInput testid="opcua-path" label="Path" value={cfg.opcua.path} onChange={(v) => update('opcua', 'path', v)} />
          <TextInput testid="opcua-namespace" label="Namespace" value={cfg.opcua.namespace} onChange={(v) => update('opcua', 'namespace', v)} className="md:col-span-2" />
          <NumberInput testid="opcua-interval" label="Intervalo" unit="ms" value={cfg.opcua.interval} onChange={(v) => update('opcua', 'interval', v)} />
        </div>
        <p className="font-mono text-[11px] text-slate-500 mt-3">Endpoint: opc.tcp://{cfg.opcua.host}:{cfg.opcua.port}{cfg.opcua.path}</p>
      </Card>

      {/* Simulación + Persistencia */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-px hair-grid">
        <Card className="p-5" testid="config-sim">
          <SectionTitle kicker="06">Simulación</SectionTitle>
          <div className="mt-3">
            <NumberInput testid="sim-acel" label="Aceleración" value={cfg.simulacion.aceleracion} onChange={(v) => update('simulacion', 'aceleracion', v)} step={1} min={1} max={500} />
            <p className="text-xs text-slate-500 font-mono mt-2">1 = tiempo real · 60 = 1 minuto real por segundo</p>
          </div>
        </Card>

        <Card className="p-5" testid="config-persist">
          <SectionTitle kicker="07">Persistencia automática</SectionTitle>
          <div className="space-y-3 mt-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Auto-guardado CSV</span>
              <Toggle testid="persist-toggle" value={cfg.persistence.enabled} onChange={(v) => update('persistence', 'enabled', v)} label={cfg.persistence.enabled ? 'Activo' : 'Pausado'} />
            </div>
            <NumberInput testid="persist-interval" label="Intervalo" unit="s" value={cfg.persistence.interval_seconds} onChange={(v) => update('persistence', 'interval_seconds', v)} min={1} max={3600} />
            <p className="text-xs text-slate-500 font-mono">Archivos diarios en backend/data/yerba_history_YYYY-MM-DD.csv</p>
          </div>
        </Card>
      </div>

      {/* Archivos */}
      <Card className="p-5" testid="config-files">
        <div className="flex items-center justify-between mb-3">
          <SectionTitle kicker="08">Histórico CSV / Excel</SectionTitle>
          <Btn testid="files-refresh" variant="secondary" onClick={() => api.listDataFiles().then(setFiles)}>Refrescar</Btn>
        </div>
        {files.length === 0 ? (
          <p className="font-mono text-xs text-slate-500">No hay archivos todavía. El primer guardado ocurrirá en {cfg.persistence.interval_seconds || 5}s.</p>
        ) : (
          <div className="border" style={{ borderColor: 'var(--border)' }}>
            {files.map((f, i) => (
              <div key={f.name} className="flex items-center justify-between px-3 py-2 border-b last:border-b-0 font-mono text-xs" style={{ borderColor: 'var(--border)' }} data-testid={`file-row-${i}`}>
                <span className="text-slate-200">{f.name}</span>
                <span className="text-slate-500">{(f.size / 1024).toFixed(1)} KB</span>
                <div className="flex gap-2">
                  <a href={api.downloadCsvUrl(f.name)} className="text-slate-300 hover:text-amber-300" data-testid={`download-csv-${i}`} download><Download size={14} className="inline mr-1"/>CSV</a>
                  <a href={api.excelUrl(f.name)} className="text-slate-300 hover:text-amber-300" data-testid={`download-xlsx-${i}`} download><Download size={14} className="inline mr-1"/>XLSX</a>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="mt-3">
          <a href={api.excelUrl(null)} download className="inline-block" data-testid="download-all-xlsx">
            <Btn variant="ai">Exportar TODO el histórico como Excel</Btn>
          </a>
        </div>
      </Card>

      {/* Guardar */}
      <div className="surface p-5 flex items-center justify-between" data-testid="config-save-row">
        <span className="font-mono text-xs text-slate-400">{savedMsg || 'Los cambios se aplican al archivo backend/config_yerba.yaml'}</span>
        <Btn testid="config-save-btn" onClick={save} disabled={saving}>
          <span className="inline-flex items-center gap-1"><FloppyDisk size={13}/> {saving ? 'Guardando...' : 'Guardar configuración'}</span>
        </Btn>
      </div>
    </div>
  );
}

function ServiceCell({ label, s, format, testid }) {
  const state = s?.running ? 'online' : s?.error ? 'offline' : 'warning';
  return (
    <div className="border p-3" style={{ borderColor: 'var(--border)' }} data-testid={testid}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-slate-400">{label}</span>
        <StatusBadge state={state} label={state === 'online' ? 'ON' : state === 'offline' ? 'ERR' : 'OFF'} testid={`${testid}-badge`} />
      </div>
      <div className="text-slate-200 truncate">{s ? format(s) : '–'}</div>
      {s?.error && <div className="text-red-400 text-[10px] truncate" title={s.error}>{s.error}</div>}
    </div>
  );
}

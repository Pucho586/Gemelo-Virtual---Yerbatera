import React, { useEffect, useState } from 'react';
import './App.css';
import { useLiveState } from './lib/useLiveState';
import { api } from './lib/api';
import { StatusBadge } from './components/UI';
import Dashboard from './components/Dashboard';
import ZapecadoView from './components/ZapecadoView';
import SecadoView from './components/SecadoView';
import CanchadoView from './components/CanchadoView';
import CamarasView from './components/CamarasView';
import AIPanel from './components/AIPanel';
import ConfigView from './components/ConfigView';
import { Leaf, House, Fire, Drop, Cube, Cloud, Gear, Sparkle } from '@phosphor-icons/react';

const TABS = [
  { id: 'dashboard', label: 'Dashboard', Icon: House },
  { id: 'zapecado', label: 'Zapecado', Icon: Fire },
  { id: 'secado', label: 'Secado', Icon: Drop },
  { id: 'canchado', label: 'Canchado', Icon: Cube },
  { id: 'camaras', label: 'Cámaras', Icon: Cloud },
  { id: 'ia', label: 'IA · Gemini', Icon: Sparkle },
  { id: 'config', label: 'Configuración', Icon: Gear },
];

function App() {
  const [tab, setTab] = useState('dashboard');
  const { state, connected, series } = useLiveState({ historyLength: 180 });
  const [status, setStatus] = useState(null);

  useEffect(() => {
    const fetch = () => api.servicesStatus().then(setStatus).catch(() => {});
    fetch();
    const id = setInterval(fetch, 10000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="App min-h-screen" style={{ background: 'var(--bg)' }}>
      {/* TOP BAR */}
      <header className="border-b" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center gap-6 justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 flex items-center justify-center bg-amber-300/10 border border-amber-300/30" data-testid="app-logo">
              <Leaf size={18} className="text-amber-300" weight="duotone" />
            </div>
            <div className="leading-tight">
              <div className="font-display text-sm font-semibold text-slate-100 tracking-tight">Gemelo Digital · Yerba Mate</div>
              <div className="font-mono text-[10px] text-slate-500 tracking-wider uppercase">Yerbatera Industrial Twin · v2.0</div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap" data-testid="header-status-row">
            <StatusBadge state={connected ? 'online' : 'warning'} label={connected ? 'WS live' : 'polling'} testid="conn-badge" />
            <StatusBadge state={status?.modbus?.running ? 'online' : 'offline'} label="Modbus" testid="modbus-badge" />
            <StatusBadge state={status?.mqtt?.running ? 'online' : 'offline'} label="MQTT" testid="mqtt-badge" />
            <StatusBadge state={status?.opcua?.running ? 'online' : 'offline'} label="OPC UA" testid="opcua-badge" />
            <StatusBadge state={status?.weather?.running ? 'online' : 'offline'} label="Clima" testid="weather-badge" />
          </div>
        </div>

        {/* TABS */}
        <nav className="max-w-[1920px] mx-auto px-2 sm:px-4 lg:px-6 flex items-center overflow-x-auto" data-testid="tabs-nav">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              data-testid={`tab-${id}`}
              onClick={() => setTab(id)}
              className={`px-4 py-2.5 text-sm font-medium tracking-tight inline-flex items-center gap-2 border-b-2 transition-colors whitespace-nowrap ${tab === id ? 'border-amber-300 text-slate-100' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
            >
              <Icon size={15} weight={tab === id ? 'fill' : 'regular'} />
              {label}
            </button>
          ))}
        </nav>
      </header>

      {/* CONTENT */}
      <main className="max-w-[1920px] mx-auto p-4 sm:p-6 lg:p-8" data-testid="main-content">
        {tab === 'dashboard' && <Dashboard state={state} series={series} status={status} />}
        {tab === 'zapecado' && <ZapecadoView state={state} series={series} />}
        {tab === 'secado' && <SecadoView state={state} series={series} />}
        {tab === 'canchado' && <CanchadoView state={state} series={series} />}
        {tab === 'camaras' && <CamarasView state={state} series={series} />}
        {tab === 'ia' && <AIPanel />}
        {tab === 'config' && <ConfigView status={status} />}
      </main>

      <footer className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-6 border-t mt-8" style={{ borderColor: 'var(--border)' }}>
        <div className="flex flex-wrap items-center justify-between gap-3 font-mono text-[10px] text-slate-500 uppercase tracking-wider">
          <span>Yerbatera Twin · Powered by FastAPI · Gemini 3 Flash · Open-Meteo</span>
          <span>{state?.ts ? new Date(state.ts).toLocaleTimeString() : '–'}</span>
        </div>
      </footer>
    </div>
  );
}

export default App;

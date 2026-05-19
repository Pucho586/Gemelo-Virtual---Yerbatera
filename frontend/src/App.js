import React, { useEffect, useState } from 'react';
import './App.css';
import { useLiveState } from './lib/useLiveState';
import { api } from './lib/api';
import { AuthProvider, useAuth, isAdmin } from './lib/auth';
import { StatusBadge, Btn } from './components/UI';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import ZapecadoView from './components/ZapecadoView';
import SecadoView from './components/SecadoView';
import CanchadoView from './components/CanchadoView';
import CamarasView from './components/CamarasView';
import AIPanel from './components/AIPanel';
import ConfigView from './components/ConfigView';
import RecetasView from './components/RecetasView';
import LotesView from './components/LotesView';
import Industria40View from './components/Industria40View';
import { Leaf, House, Fire, Drop, Cube, Cloud, Gear, Sparkle, ForkKnife, Package, SignOut, Cpu, Robot, Plugs } from '@phosphor-icons/react';

const TABS = [
  { id: 'dashboard', label: 'Dashboard', Icon: House, role: 'any' },
  { id: 'zapecado', label: 'Zapecado', Icon: Fire, role: 'any' },
  { id: 'secado', label: 'Secado', Icon: Drop, role: 'any' },
  { id: 'canchado', label: 'Canchado', Icon: Cube, role: 'any' },
  { id: 'camaras', label: 'Cámaras', Icon: Cloud, role: 'any' },
  { id: 'recetas', label: 'Recetas', Icon: ForkKnife, role: 'any' },
  { id: 'lotes', label: 'Lotes', Icon: Package, role: 'any' },
  { id: 'i40', label: 'Industria 4.0', Icon: Plugs, role: 'any' },
  { id: 'ia', label: 'IA · Gemini', Icon: Sparkle, role: 'any' },
  { id: 'config', label: 'Configuración', Icon: Gear, role: 'admin' },
];

function AuthedApp() {
  const { user, logout } = useAuth();
  const [tab, setTab] = useState('dashboard');
  const { state, connected, series } = useLiveState({ historyLength: 240 });
  const [status, setStatus] = useState(null);
  const [mode, setMode] = useState('simulator');
  const [mimicStyle, setMimicStyle] = useState(() => {
    try { return localStorage.getItem('yerba_mimic') || 'svg'; } catch (e) { return 'svg'; }
  });

  useEffect(() => {
    const fetch = () => Promise.all([
      api.servicesStatus().catch(() => null),
      api.getMode().catch(() => null),
    ]).then(([s, m]) => {
      if (s) setStatus(s);
      if (m) setMode(m.mode);
    });
    fetch();
    const id = setInterval(fetch, 10000);
    return () => clearInterval(id);
  }, []);

  const toggleMode = async () => {
    if (!isAdmin(user)) return;
    // 3-way cycle: simulator → shadow → twin → simulator
    const next = mode === 'simulator' ? 'shadow' : mode === 'shadow' ? 'twin' : 'simulator';
    try {
      await api.setMode(next);
      setMode(next);
    } catch (e) {
      alert(e?.response?.data?.detail || 'Error');
    }
  };

  const modeMeta = {
    simulator: { label: 'Simulador', cls: 'bg-green-500/10 text-green-400 border-green-500/30', Icon: Robot },
    shadow:    { label: 'Shadow',    cls: 'bg-blue-500/10 text-blue-300 border-blue-500/30', Icon: Cpu },
    twin:      { label: 'Gemelo',    cls: 'bg-amber-300/15 text-amber-300 border-amber-300/40', Icon: Cpu },
  };
  const mm = modeMeta[mode] || modeMeta.simulator;

  const toggleMimic = () => {
    const next = mimicStyle === 'svg' ? 'pid' : 'svg';
    setMimicStyle(next);
    try { localStorage.setItem('yerba_mimic', next); } catch (e) { /* ignore */ }
  };

  const visibleTabs = TABS.filter(t => t.role === 'any' || isAdmin(user));

  return (
    <div className="App min-h-screen" style={{ background: 'var(--bg)' }}>
      <header className="border-b" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center gap-4 flex-wrap justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 flex items-center justify-center bg-amber-300/10 border border-amber-300/30" data-testid="app-logo">
              <Leaf size={18} className="text-amber-300" weight="duotone" />
            </div>
            <div className="leading-tight">
              <div className="font-display text-sm font-semibold text-slate-100 tracking-tight">Gemelo Digital · Yerba Mate</div>
              <div className="font-mono text-[10px] text-slate-500 tracking-wider uppercase">v2.1 · {user?.display}</div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              data-testid="mode-switch"
              onClick={toggleMode}
              disabled={!isAdmin(user)}
              className={`inline-flex items-center gap-2 px-3 py-1.5 text-xs font-mono uppercase tracking-wider border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${mm.cls}`}
              title={isAdmin(user) ? 'Ciclar modo: Simulador → Shadow → Gemelo' : 'Requiere admin'}
            >
              <mm.Icon size={13} weight="duotone" /> Modo {mm.label}
            </button>
            <StatusBadge state={connected ? 'online' : 'warning'} label={connected ? 'WS' : 'POLL'} testid="conn-badge" />
            <StatusBadge state={status?.modbus?.running ? 'online' : 'offline'} label="Modbus" testid="modbus-badge" />
            <StatusBadge state={status?.mqtt?.running ? 'online' : 'offline'} label="MQTT" testid="mqtt-badge" />
            <StatusBadge state={status?.opcua?.running ? 'online' : 'offline'} label="OPC UA" testid="opcua-badge" />
            <StatusBadge state={status?.weather?.running ? 'online' : 'offline'} label="Clima" testid="weather-badge" />
            <button onClick={toggleMimic} className="text-xs font-mono text-slate-400 hover:text-amber-300 transition-colors border border-[#232A26] px-2 py-1" data-testid="mimic-toggle" title="Estilo de mímicos">
              {mimicStyle === 'svg' ? 'SVG' : 'P&ID'}
            </button>
            <button onClick={logout} className="inline-flex items-center gap-1 text-xs font-mono text-slate-400 hover:text-red-400 transition-colors border border-[#232A26] px-2 py-1" data-testid="logout-btn">
              <SignOut size={12} /> Salir
            </button>
          </div>
        </div>

        <nav className="max-w-[1920px] mx-auto px-2 sm:px-4 lg:px-6 flex items-center overflow-x-auto" data-testid="tabs-nav">
          {visibleTabs.map(({ id, label, Icon }) => (
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

      {/* TABS PERSISTENTES: todas montadas, solo se oculta con CSS */}
      <main className="max-w-[1920px] mx-auto p-4 sm:p-6 lg:p-8" data-testid="main-content">
        <div style={{ display: tab === 'dashboard' ? 'block' : 'none' }}><Dashboard state={state} series={series} status={status} /></div>
        <div style={{ display: tab === 'zapecado' ? 'block' : 'none' }}><ZapecadoView state={state} series={series} mimicStyle={mimicStyle} /></div>
        <div style={{ display: tab === 'secado' ? 'block' : 'none' }}><SecadoView state={state} series={series} mimicStyle={mimicStyle} /></div>
        <div style={{ display: tab === 'canchado' ? 'block' : 'none' }}><CanchadoView state={state} series={series} mimicStyle={mimicStyle} /></div>
        <div style={{ display: tab === 'camaras' ? 'block' : 'none' }}><CamarasView state={state} series={series} mimicStyle={mimicStyle} /></div>
        <div style={{ display: tab === 'recetas' ? 'block' : 'none' }}><RecetasView /></div>
        <div style={{ display: tab === 'lotes' ? 'block' : 'none' }}><LotesView /></div>
        <div style={{ display: tab === 'i40' ? 'block' : 'none' }}><Industria40View /></div>
        <div style={{ display: tab === 'ia' ? 'block' : 'none' }}><AIPanel /></div>
        {isAdmin(user) && (
          <div style={{ display: tab === 'config' ? 'block' : 'none' }}><ConfigView status={status} /></div>
        )}
      </main>

      <footer className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-6 border-t mt-8" style={{ borderColor: 'var(--border)' }}>
        <div className="flex flex-wrap items-center justify-between gap-3 font-mono text-[10px] text-slate-500 uppercase tracking-wider">
          <span>Yerbatera Twin · {mode === 'twin' ? 'Lectura de fuente externa' : mode === 'shadow' ? 'Simulación + comparación con PLC' : 'Simulación matemática'} · Gemini 3 Flash · Open-Meteo</span>
          <span>{state?.ts ? new Date(state.ts).toLocaleTimeString() : '–'}</span>
        </div>
      </footer>
    </div>
  );
}

function Root() {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="min-h-screen flex items-center justify-center font-mono text-slate-500" style={{ background: 'var(--bg)' }}>Cargando...</div>;
  }
  if (!user) return <Login />;
  return <AuthedApp />;
}

function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}

export default App;

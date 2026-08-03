import React, { useEffect, useState } from 'react';
import './App.css';
import { useLiveState } from './lib/useLiveState';
import { api } from './lib/api';
import { AuthProvider, useAuth, isAdmin } from './lib/auth';
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
import ProtocolsView from './components/ProtocolsView';
import DocenteView from './components/DocenteView';
import BankSelector from './components/BankSelector';
import OperacionesView from './components/OperacionesView';
import Fase4View from './components/Fase4View';
import MassFlowView from './components/MassFlowView';
import DocsModal from './components/DocsModal';
import TourModal from './components/TourModal';
import SpeedControl from './components/SpeedControl';
import WeatherControl from './components/WeatherControl';
import { Leaf, House, Fire, Drop, Cube, Cloud, Gear, Sparkle, ForkKnife, Package, SignOut, Cpu, Robot, Plugs, ChartLineUp, Bell, Flask, FlowArrow, BookOpen, GraduationCap, Broadcast, Play } from '@phosphor-icons/react';

const TABS = [
  { id: 'dashboard', label: 'Dashboard', Icon: House, role: 'any' },
  { id: 'massflow', label: 'Flujo de masa', Icon: FlowArrow, role: 'any' },
  { id: 'zapecado', label: 'Zapecado', Icon: Fire, role: 'any' },
  { id: 'secado', label: 'Secado', Icon: Drop, role: 'any' },
  { id: 'canchado', label: 'Canchado', Icon: Cube, role: 'any' },
  { id: 'camaras', label: 'Cámaras', Icon: Cloud, role: 'any' },
  { id: 'recetas', label: 'Recetas', Icon: ForkKnife, role: 'any' },
  { id: 'lotes', label: 'Lotes', Icon: Package, role: 'any' },
  { id: 'ops', label: 'Operaciones', Icon: ChartLineUp, role: 'any' },
  { id: 'protocolos', label: 'Protocolos', Icon: Broadcast, role: 'any' },
  { id: 'i40', label: 'Industria 4.0', Icon: Plugs, role: 'any' },
  { id: 'fase4', label: 'Replay & What-if', Icon: Flask, role: 'any' },
  { id: 'ia', label: 'IA · Gemini', Icon: Sparkle, role: 'any' },
  { id: 'docente', label: 'Docente', Icon: GraduationCap, role: 'admin' },
  { id: 'config', label: 'Configuración', Icon: Gear, role: 'admin' },
];
const TAB_META = Object.fromEntries(TABS.map(t => [t.id, t]));

// Navegación de dos niveles: 4 grupos temáticos en vez de 13 tabs sueltas.
const GROUPS = [
  { id: 'operacion', label: 'Operación', Icon: House, tabs: ['dashboard', 'massflow', 'recetas', 'lotes'] },
  { id: 'proceso', label: 'Proceso', Icon: Fire, tabs: ['zapecado', 'secado', 'canchado', 'camaras'] },
  { id: 'analisis', label: 'Análisis', Icon: ChartLineUp, tabs: ['ops', 'fase4', 'ia'] },
  { id: 'integracion', label: 'Integración', Icon: Plugs, tabs: ['protocolos', 'i40', 'docente', 'config'] },
];

function ConnDot({ on, disabled, label, testid }) {
  const color = disabled ? 'text-slate-600' : on ? 'text-green-400' : 'text-red-400';
  return (
    <span className="inline-flex items-center gap-1.5" data-testid={testid} title={disabled ? `${label}: desactivado` : on ? `${label}: activo` : `${label}: sin conexión`}>
      <span className={`${on && !disabled ? 'live-dot ' : ''}${color} text-[9px]`}>●</span>
      <span className="font-mono text-[11px] tracking-wide text-slate-400">{label}</span>
    </span>
  );
}

function AuthedApp() {
  const { user, logout } = useAuth();
  const [tab, setTab] = useState('dashboard');
  const { state, connected, series } = useLiveState({ historyLength: 240 });
  const [status, setStatus] = useState(null);
  const [mode, setMode] = useState('simulator');
  const [activeAlarms, setActiveAlarms] = useState(0);
  const [mimicStyle, setMimicStyle] = useState(() => {
    try { return localStorage.getItem('yerba_mimic') || 'svg'; } catch (e) { return 'svg'; }
  });
  const [animated, setAnimated] = useState(() => {
    try { return localStorage.getItem('yerba_animated') !== 'off'; } catch (e) { return true; }
  });
  const [docsOpen, setDocsOpen] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);

  // Autoabrir tour la primera vez (después de login)
  useEffect(() => {
    if (!user) return;
    try {
      const seen = localStorage.getItem('yerba_tour_seen');
      if (!seen) setTourOpen(true);
    } catch (e) { /* ignore */ }
  }, [user]);

  useEffect(() => {
    const fetch = () => Promise.all([
      api.servicesStatus().catch(() => null),
      api.getMode().catch(() => null),
      api.alarmsActive().catch(() => []),
    ]).then(([s, m, al]) => {
      if (s) setStatus(s);
      if (m) setMode(m.mode);
      setActiveAlarms((al || []).length);
    });
    fetch();
    const id = setInterval(fetch, 8000);
    return () => clearInterval(id);
  }, []);

  const toggleMode = async () => {
    if (!isAdmin(user)) return;
    // 3-way cycle: simulator → shadow → twin → simulator. Replay se entra desde Fase4 tab.
    const cycle = { simulator: 'shadow', shadow: 'twin', twin: 'simulator', replay: 'simulator' };
    const next = cycle[mode] || 'simulator';
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
    replay:    { label: 'Replay',    cls: 'bg-purple-500/15 text-purple-300 border-purple-500/40', Icon: Cpu },
  };
  const mm = modeMeta[mode] || modeMeta.simulator;

  const toggleMimic = () => {
    const next = mimicStyle === 'svg' ? 'pid' : 'svg';
    setMimicStyle(next);
    try { localStorage.setItem('yerba_mimic', next); } catch (e) { /* ignore */ }
  };

  const toggleAnimated = () => {
    setAnimated(prev => {
      const next = !prev;
      try { localStorage.setItem('yerba_animated', next ? 'on' : 'off'); } catch (e) { /* ignore */ }
      return next;
    });
  };

  const canSee = (id) => { const t = TAB_META[id]; return t && (t.role === 'any' || isAdmin(user)); };
  const visibleGroups = GROUPS
    .map(g => ({ ...g, tabs: g.tabs.filter(canSee) }))
    .filter(g => g.tabs.length > 0);
  const activeGroup = visibleGroups.find(g => g.tabs.includes(tab)) || visibleGroups[0];
  const subTabs = (activeGroup?.tabs || []).map(id => TAB_META[id]);
  const selectGroup = (g) => { if (!g.tabs.includes(tab)) setTab(g.tabs[0]); };

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
              <div className="font-mono text-[10px] text-slate-500 tracking-wider uppercase">v2.4 · {user?.display}</div>
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
            {/* Cluster de conexión agrupado: un solo bloque en vez de 4 badges sueltos */}
            <div className="inline-flex items-center gap-3 px-2.5 py-1 border" style={{ borderColor: 'var(--border)' }} title="Estado de enlaces" data-testid="conn-cluster">
              <ConnDot on={connected} label={connected ? 'WS' : 'POLL'} testid="conn-badge" />
              <ConnDot on={status?.modbus?.running} disabled={status?.modbus?.disabled} label="MB" testid="modbus-badge" />
              <ConnDot on={status?.mqtt?.running} disabled={status?.mqtt?.disabled} label="MQTT" testid="mqtt-badge" />
              <ConnDot on={status?.opcua?.running} disabled={status?.opcua?.disabled} label="OPC" testid="opcua-badge" />
            </div>
            <BankSelector />
            <WeatherControl ambient={state?.ambient} weatherStatus={status?.weather} />
            {activeAlarms > 0 && (
              <button onClick={() => setTab('ops')} className="inline-flex items-center gap-1 px-2 py-1 text-xs font-mono uppercase tracking-wider border bg-red-500/15 text-red-300 border-red-500/40 hover:bg-red-500/25 transition-colors" data-testid="alarms-badge-header">
                <Bell size={12} weight="fill" /> {activeAlarms} alarm{activeAlarms === 1 ? 'a' : 'as'}
              </button>
            )}
            <button onClick={toggleMimic} className="text-xs font-mono text-slate-400 hover:text-amber-300 transition-colors border border-[#232A26] px-2 py-1" data-testid="mimic-toggle" title="Estilo de mímicos">
              {mimicStyle === 'svg' ? 'SVG' : 'P&ID'}
            </button>
            <button onClick={toggleAnimated} className={`inline-flex items-center gap-1 text-xs font-mono transition-colors border px-2 py-1 ${animated ? 'text-amber-300 border-amber-500/40' : 'text-slate-500 border-[#232A26]'}`} data-testid="animated-toggle" title={animated ? 'Animaciones activadas — clic para pausar' : 'Animaciones pausadas — clic para activar'}>
              <Play size={12} weight={animated ? 'fill' : 'regular'} /> {animated ? 'Animación' : 'Estático'}
            </button>
            <SpeedControl />
            <button onClick={() => setTourOpen(true)} className="inline-flex items-center gap-1 text-xs font-mono text-amber-300 hover:text-amber-200 transition-colors border border-amber-500/40 px-2 py-1" data-testid="tour-open-btn" title="Tour guiado de primer turno">
              <GraduationCap size={12} /> Tour
            </button>
            <button onClick={() => setDocsOpen(true)} className="inline-flex items-center gap-1 text-xs font-mono text-amber-300 hover:text-amber-200 transition-colors border border-amber-500/40 px-2 py-1" data-testid="docs-open-btn" title="Manuales del sistema">
              <BookOpen size={12} /> Manual
            </button>
            <button onClick={logout} className="inline-flex items-center gap-1 text-xs font-mono text-slate-400 hover:text-red-400 transition-colors border border-[#232A26] px-2 py-1" data-testid="logout-btn">
              <SignOut size={12} /> Salir
            </button>
          </div>
        </div>

        {/* Nivel 1: grupos temáticos */}
        <nav className="max-w-[1920px] mx-auto px-2 sm:px-4 lg:px-6 flex items-center gap-1 overflow-x-auto" data-testid="groups-nav">
          {visibleGroups.map((g) => {
            const on = activeGroup?.id === g.id;
            return (
              <button
                key={g.id}
                data-testid={`group-${g.id}`}
                onClick={() => selectGroup(g)}
                className={`px-4 py-3 text-sm font-semibold tracking-tight inline-flex items-center gap-2 border-b-2 transition-colors whitespace-nowrap ${on ? 'border-amber-300 text-slate-100' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
              >
                <g.Icon size={16} weight={on ? 'fill' : 'regular'} />
                {g.label}
              </button>
            );
          })}
        </nav>
      </header>

      {/* Nivel 2: vistas dentro del grupo activo */}
      <div className="border-b" style={{ borderColor: 'var(--border)', background: 'var(--bg)' }}>
        <nav className="max-w-[1920px] mx-auto px-2 sm:px-4 lg:px-6 flex items-center gap-1 overflow-x-auto" data-testid="tabs-nav">
          {subTabs.map(({ id, label, Icon }) => (
            <button
              key={id}
              data-testid={`tab-${id}`}
              onClick={() => setTab(id)}
              className={`px-3.5 py-2 text-[13px] font-medium tracking-tight inline-flex items-center gap-1.5 rounded-md my-1.5 transition-colors whitespace-nowrap ${tab === id ? 'bg-amber-300/10 text-amber-200' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'}`}
            >
              <Icon size={14} weight={tab === id ? 'fill' : 'regular'} />
              {label}
            </button>
          ))}
        </nav>
      </div>

      {/* TABS PERSISTENTES: todas montadas, solo se oculta con CSS */}
      <main className="max-w-[1920px] mx-auto p-4 sm:p-6 lg:p-8" data-testid="main-content">
        <div style={{ display: tab === 'dashboard' ? 'block' : 'none' }}><Dashboard state={state} series={series} status={status} /></div>
        <div style={{ display: tab === 'massflow' ? 'block' : 'none' }}><MassFlowView /></div>
        <div style={{ display: tab === 'zapecado' ? 'block' : 'none' }}><ZapecadoView state={state} series={series} mimicStyle={mimicStyle} animated={animated} /></div>
        <div style={{ display: tab === 'secado' ? 'block' : 'none' }}><SecadoView state={state} series={series} mimicStyle={mimicStyle} animated={animated} /></div>
        <div style={{ display: tab === 'canchado' ? 'block' : 'none' }}><CanchadoView state={state} series={series} mimicStyle={mimicStyle} animated={animated} /></div>
        <div style={{ display: tab === 'camaras' ? 'block' : 'none' }}><CamarasView state={state} series={series} mimicStyle={mimicStyle} animated={animated} /></div>
        <div style={{ display: tab === 'recetas' ? 'block' : 'none' }}><RecetasView /></div>
        <div style={{ display: tab === 'lotes' ? 'block' : 'none' }}><LotesView /></div>
        <div style={{ display: tab === 'ops' ? 'block' : 'none' }}><OperacionesView /></div>
        <div style={{ display: tab === 'protocolos' ? 'block' : 'none' }}><ProtocolsView /></div>
        <div style={{ display: tab === 'i40' ? 'block' : 'none' }}><Industria40View /></div>
        <div style={{ display: tab === 'fase4' ? 'block' : 'none' }}><Fase4View /></div>
        <div style={{ display: tab === 'ia' ? 'block' : 'none' }}><AIPanel /></div>
        {isAdmin(user) && (
          <div style={{ display: tab === 'docente' ? 'block' : 'none' }}><DocenteView /></div>
        )}
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
      {docsOpen && <DocsModal onClose={() => setDocsOpen(false)} />}
      {tourOpen && <TourModal onClose={() => setTourOpen(false)} onJumpTab={(t) => { setTab(t); setTourOpen(false); }} />}
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

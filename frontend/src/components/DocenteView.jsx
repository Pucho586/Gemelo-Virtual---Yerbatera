import React, { useEffect, useState, useCallback } from 'react';
import { Card, CardHeader, Metric, Btn, SectionTitle } from './UI';
import { api, setBank } from '../lib/api';
import { GraduationCap, Snowflake, ArrowClockwise, Trash, Warning, Target, Play, Pause, Desktop } from '@phosphor-icons/react';

// Fallas rápidas que el docente puede inyectar por etapa.
const FAULTS = {
  zapecado: [
    { key: 'falla_quemador', label: 'Falla quemador' },
    { key: 'falla_motor_tambor', label: 'Falla motor tambor' },
  ],
  secado: [
    { key: 'falla_ventilador', label: 'Falla ventilador' },
    { key: 'falla_serpentin', label: 'Falla serpentín' },
  ],
  canchado: [
    { key: 'falla_motor', label: 'Falla motor molino' },
    { key: 'rodamiento_caliente', label: 'Rodamiento caliente' },
  ],
};

function InjectPanel({ bankId, onDone }) {
  const [stage, setStage] = useState('zapecado');
  const [busy, setBusy] = useState(false);

  const inject = async (patch) => {
    setBusy(true);
    try {
      await api.bankInject(bankId, { stage, patch });
      onDone && onDone();
    } catch (e) {
      alert('No se pudo inyectar: ' + (e?.response?.data?.detail || e.message));
    } finally { setBusy(false); }
  };

  return (
    <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
      <div className="flex items-center gap-2 mb-2">
        <Warning size={13} className="text-amber-300" weight="duotone" />
        <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Inyectar falla</span>
        <select value={stage} onChange={e => setStage(e.target.value)}
          className="ml-auto bg-transparent border border-[#232A26] text-[11px] font-mono text-slate-200 px-1.5 py-0.5 focus:outline-none">
          <option value="zapecado">Zapecado</option>
          <option value="secado">Secado</option>
          <option value="canchado">Canchado</option>
        </select>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {(FAULTS[stage] || []).map(f => (
          <button key={f.key} disabled={busy}
            onClick={() => inject({ [f.key]: true })}
            className="text-[11px] font-mono px-2 py-1 border border-red-500/40 text-red-300 hover:bg-red-500/10 disabled:opacity-50">
            ⚠ {f.label}
          </button>
        ))}
        {(FAULTS[stage] || []).map(f => (
          <button key={f.key + '-off'} disabled={busy}
            onClick={() => inject({ [f.key]: false })}
            className="text-[11px] font-mono px-2 py-1 border border-[#232A26] text-slate-400 hover:bg-white/5 disabled:opacity-50">
            ✓ Sanar {f.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ConsignaPanel({ bank, onSaved }) {
  const [title, setTitle] = useState(bank.consigna?.title || '');
  const [desc, setDesc] = useState(bank.consigna?.description || '');
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await api.bankConsigna(bank.id, { title: title.trim() || null, description: desc.trim() || null });
      onSaved && onSaved();
    } catch (e) {
      alert('No se pudo guardar la consigna: ' + (e?.response?.data?.detail || e.message));
    } finally { setBusy(false); }
  };

  return (
    <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
      <div className="flex items-center gap-2 mb-2">
        <Target size={13} className="text-emerald-300" weight="duotone" />
        <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Consigna del alumno</span>
      </div>
      <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Título (ej. Controlar zapecado a 450°C)"
        className="w-full bg-transparent border border-[#232A26] text-xs font-mono text-slate-200 px-2 py-1 mb-1.5 focus:outline-none focus:border-emerald-400" />
      <textarea value={desc} onChange={e => setDesc(e.target.value)} rows={2} placeholder="Descripción / criterio de aprobación"
        className="w-full bg-transparent border border-[#232A26] text-xs font-mono text-slate-200 px-2 py-1 focus:outline-none focus:border-emerald-400 resize-y" />
      <div className="flex justify-end mt-1.5">
        <button onClick={save} disabled={busy} className="text-[11px] font-mono px-3 py-1 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-50">
          Guardar consigna
        </button>
      </div>
    </div>
  );
}

function BankCard({ bank, onChange }) {
  const s = bank.snapshot || {};
  const isDefault = bank.id === 'default';

  const doFreeze = async () => { try { await api.bankFreeze(bank.id, !bank.frozen); onChange(); } catch (e) { alert(e.message); } };
  const doReset = async () => {
    if (!window.confirm(`¿Reiniciar el simulador del banco "${bank.name}"?`)) return;
    try { await api.bankReset(bank.id); onChange(); } catch (e) { alert(e.message); }
  };
  const doDelete = async () => {
    if (!window.confirm(`¿Eliminar el banco "${bank.name}"? Se pierde su estado.`)) return;
    try { await api.deleteBank(bank.id); onChange(); } catch (e) { alert(e?.response?.data?.detail || e.message); }
  };
  const openBank = () => { setBank(bank.id); window.location.reload(); };

  return (
    <Card className="p-4" testid={`bank-card-${bank.id}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-display text-sm font-semibold text-slate-100">{bank.name}</span>
            {bank.frozen && <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 bg-sky-500/15 text-sky-300 border border-sky-500/40">Congelado</span>}
            {isDefault && <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 text-slate-500 border border-[#232A26]">principal</span>}
          </div>
          <div className="font-mono text-[10px] text-slate-500 mt-0.5">
            {bank.student ? `👤 ${bank.student} · ` : ''}MB:{bank.ports?.modbus} · OPC:{bank.ports?.opcua} · {bank.ports?.mqtt_prefix}
          </div>
        </div>
        <button onClick={openBank} className="text-[11px] font-mono px-2 py-1 border border-sky-500/40 text-sky-300 hover:bg-sky-500/10 inline-flex items-center gap-1" title="Operar este banco">
          <Desktop size={12} /> Abrir
        </button>
      </div>

      <div className="grid grid-cols-3 gap-2 mt-3">
        <Metric label="Zap T" value={(s.zapecado_temp ?? 0).toFixed ? s.zapecado_temp.toFixed(0) : s.zapecado_temp} unit="°C" color="var(--temp)" testid={`bank-${bank.id}-zap`} />
        <Metric label="Sec T/HR" value={`${(s.secado_temp ?? 0).toFixed ? s.secado_temp.toFixed(0) : s.secado_temp}/${(s.secado_hum ?? 0).toFixed ? s.secado_hum.toFixed(0) : s.secado_hum}`} unit="°C/%" color="var(--amber)" testid={`bank-${bank.id}-sec`} />
        <Metric label="Canch" value={(s.canchado_part ?? 0).toFixed ? s.canchado_part.toFixed(2) : s.canchado_part} unit="mm" color="var(--green)" testid={`bank-${bank.id}-can`} />
      </div>
      <div className="flex items-center gap-3 mt-2 font-mono text-[10px] text-slate-500">
        <span>Modo: <span className="text-slate-300">{s.mode || '–'}</span></span>
        <span>Cámaras: <span className="text-slate-300">{s.camaras ?? '–'}</span></span>
        <span>Zap ctrl: <span className="text-slate-300">{s.zapecado_mode || '–'}</span></span>
      </div>

      {bank.consigna?.title && (
        <div className="mt-2 px-2 py-1.5 bg-emerald-500/5 border border-emerald-500/20">
          <div className="text-[11px] font-mono text-emerald-300">🎯 {bank.consigna.title}</div>
          {bank.consigna.description && <div className="text-[10px] text-slate-400 mt-0.5">{bank.consigna.description}</div>}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5 mt-3">
        <button onClick={doFreeze} className={`text-[11px] font-mono px-2 py-1 border inline-flex items-center gap-1 ${bank.frozen ? 'border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10' : 'border-sky-500/40 text-sky-300 hover:bg-sky-500/10'}`}>
          {bank.frozen ? <><Play size={11} /> Reanudar</> : <><Pause size={11} /> Congelar</>}
        </button>
        <button onClick={doReset} className="text-[11px] font-mono px-2 py-1 border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 inline-flex items-center gap-1">
          <ArrowClockwise size={11} /> Reset
        </button>
        {!isDefault && (
          <button onClick={doDelete} className="text-[11px] font-mono px-2 py-1 border border-red-500/40 text-red-300 hover:bg-red-500/10 inline-flex items-center gap-1">
            <Trash size={11} /> Eliminar
          </button>
        )}
      </div>

      <InjectPanel bankId={bank.id} onDone={onChange} />
      <ConsignaPanel bank={bank} onSaved={onChange} />
    </Card>
  );
}

export default function DocenteView() {
  const [banks, setBanks] = useState([]);
  const [name, setName] = useState('');
  const [student, setStudent] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setBanks(await api.listBanks()); } catch (e) { /* ignore */ }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [load]);

  const create = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await api.createBank({ name: name.trim(), student: student.trim() || null });
      setName(''); setStudent('');
      await load();
    } catch (e) {
      alert('No se pudo crear el banco: ' + (e?.response?.data?.detail || e.message));
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <Card className="p-5" testid="docente-header">
        <div className="flex items-center gap-2 mb-1">
          <GraduationCap size={18} className="text-amber-300" weight="duotone" />
          <h2 className="font-display text-lg font-semibold text-slate-100">Panel del docente · Bancos de alumnos</h2>
        </div>
        <p className="text-xs text-slate-400 font-mono leading-relaxed">
          Cada banco es un gemelo aislado con sus propios puertos (Modbus/OPC/MQTT). Creá un banco por alumno o grupo,
          monitoreá su proceso en vivo, inyectales fallas para que las resuelvan, congelá/reiniciá su simulación y asignales consignas.
        </p>
        <div className="flex flex-wrap items-end gap-2 mt-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">Nombre del banco</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Banco 3"
              className="bg-transparent border border-[#232A26] text-sm font-mono text-slate-200 px-2 py-1.5 w-40 focus:outline-none focus:border-sky-400" />
          </div>
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">Alumno / grupo</label>
            <input value={student} onChange={e => setStudent(e.target.value)} placeholder="Juan Pérez"
              className="bg-transparent border border-[#232A26] text-sm font-mono text-slate-200 px-2 py-1.5 w-40 focus:outline-none focus:border-sky-400" />
          </div>
          <Btn onClick={create} disabled={busy} testid="docente-create">＋ Crear banco</Btn>
        </div>
      </Card>

      {banks.length === 0 ? (
        <Card className="p-8 text-center" testid="docente-empty">
          <SectionTitle kicker="i">Sin bancos todavía</SectionTitle>
          <p className="text-sm text-slate-400 mt-2">Creá el primer banco para asignárselo a un alumno.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {banks.map(b => <BankCard key={b.id} bank={b} onChange={load} />)}
        </div>
      )}
    </div>
  );
}

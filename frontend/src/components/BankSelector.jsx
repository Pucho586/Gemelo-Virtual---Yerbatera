import React, { useEffect, useState } from 'react';
import { api, getBank, setBank } from '../lib/api';
import { useAuth, isAdmin } from '../lib/auth';
import { Desktop, Plus } from '@phosphor-icons/react';

/**
 * Selector de banco de trabajo (multiusuario).
 * Cada alumno opera sobre su propio banco aislado; al cambiar de banco se
 * recarga la app para reconectar el WebSocket y toda la API al banco elegido.
 */
export default function BankSelector() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [banks, setBanks] = useState([]);
  const [current, setCurrent] = useState(getBank());
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [student, setStudent] = useState('');

  const load = async () => {
    try { setBanks(await api.listBanks()); } catch (e) { /* ignore */ }
  };
  useEffect(() => { load(); }, []);

  const switchBank = (id) => {
    if (id === current) return;
    setBank(id);
    window.location.reload();
  };

  const create = async () => {
    if (!name.trim()) return;
    try {
      const b = await api.createBank({ name: name.trim(), student: student.trim() || null });
      setCreating(false); setName(''); setStudent('');
      await load();
      switchBank(b.id);
    } catch (e) {
      alert('No se pudo crear el banco: ' + (e?.response?.data?.detail || e.message));
    }
  };

  const curMeta = banks.find(b => b.id === current);

  return (
    <div className="inline-flex items-center gap-1.5" data-testid="bank-selector" title="Banco de trabajo (cada alumno el suyo)">
      <Desktop size={13} className="text-sky-300" weight="duotone" />
      <select
        value={current}
        onChange={(e) => switchBank(e.target.value)}
        className="bg-transparent border border-[#232A26] text-xs font-mono text-slate-200 px-2 py-1 focus:outline-none focus:border-sky-400"
        data-testid="bank-select"
      >
        {banks.length === 0 && <option value="default">Principal</option>}
        {banks.map(b => (
          <option key={b.id} value={b.id}>
            {b.name}{b.student ? ` · ${b.student}` : ''}{b.frozen ? ' ⏸' : ''}
          </option>
        ))}
      </select>
      {curMeta?.ports && (
        <span className="font-mono text-[10px] text-slate-500 hidden lg:inline" title="Puertos de este banco">
          MB:{curMeta.ports.modbus} · OPC:{curMeta.ports.opcua}
        </span>
      )}
      {admin && !creating && (
        <button onClick={() => setCreating(true)} className="text-slate-400 hover:text-sky-300 border border-[#232A26] px-1.5 py-1" title="Crear banco" data-testid="bank-create-btn">
          <Plus size={12} weight="bold" />
        </button>
      )}
      {admin && creating && (
        <span className="inline-flex items-center gap-1">
          <input autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="Banco 3"
            className="bg-transparent border border-sky-500/40 text-xs font-mono text-slate-200 px-1.5 py-1 w-24 focus:outline-none" />
          <input value={student} onChange={e => setStudent(e.target.value)} placeholder="alumno"
            className="bg-transparent border border-[#232A26] text-xs font-mono text-slate-200 px-1.5 py-1 w-24 focus:outline-none" />
          <button onClick={create} className="text-xs font-mono text-sky-300 border border-sky-500/40 px-2 py-1 hover:bg-sky-500/10">OK</button>
          <button onClick={() => { setCreating(false); setName(''); setStudent(''); }} className="text-xs font-mono text-slate-500 px-1">✕</button>
        </span>
      )}
    </div>
  );
}

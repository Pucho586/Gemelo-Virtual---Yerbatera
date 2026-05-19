import React, { useState } from 'react';
import { useAuth } from '../lib/auth';
import { api } from '../lib/api';
import { Leaf, Lock, ArrowRight, Key } from '@phosphor-icons/react';

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [recovery, setRecovery] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [okMsg, setOkMsg] = useState('');

  const doLogin = async (e) => {
    e?.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username.trim(), password);
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === 'string' ? d : 'Error al iniciar sesión');
    } finally {
      setLoading(false);
    }
  };

  const doRecover = async (e) => {
    e?.preventDefault();
    setError(''); setOkMsg(''); setLoading(true);
    try {
      await api.recover({ username: username.trim(), recovery_code: recoveryCode.trim(), new_password: newPwd });
      setOkMsg('Contraseña actualizada. Iniciá sesión con la nueva contraseña.');
      setRecovery(false);
      setPassword('');
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === 'string' ? d : 'No se pudo recuperar');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg)' }}>
      <div className="surface w-full max-w-md p-8 fade-in" data-testid="login-card">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-11 h-11 flex items-center justify-center bg-amber-300/10 border border-amber-300/30">
            <Leaf size={20} className="text-amber-300" weight="duotone" />
          </div>
          <div>
            <h1 className="font-display text-lg font-semibold text-slate-100">Gemelo Digital · Yerba Mate</h1>
            <p className="font-mono text-[10px] text-slate-500 uppercase tracking-wider">Yerbatera Industrial Twin · v2.1</p>
          </div>
        </div>

        {!recovery ? (
          <form onSubmit={doLogin} className="space-y-4" data-testid="login-form">
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">Usuario</label>
              <input data-testid="login-username" autoFocus value={username} onChange={e => setUsername(e.target.value)} className="field w-full" placeholder="admin" />
            </div>
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">Contraseña</label>
              <input data-testid="login-password" type="password" value={password} onChange={e => setPassword(e.target.value)} className="field w-full" placeholder="••••••" />
            </div>
            {error && <div className="text-xs font-mono text-red-400 border-l-2 border-red-500/40 pl-2" data-testid="login-error">{error}</div>}
            {okMsg && <div className="text-xs font-mono text-green-400 border-l-2 border-green-500/40 pl-2">{okMsg}</div>}
            <button type="submit" disabled={loading} data-testid="login-submit" className="w-full bg-slate-50 text-slate-900 hover:bg-slate-200 transition-colors py-2.5 font-medium tracking-tight disabled:opacity-50 inline-flex items-center justify-center gap-2">
              <Lock size={14}/> {loading ? 'Ingresando...' : 'Iniciar sesión'} <ArrowRight size={14}/>
            </button>
            <button type="button" onClick={() => { setRecovery(true); setError(''); setOkMsg(''); }} className="w-full text-xs font-mono text-amber-300/80 hover:text-amber-300 transition-colors" data-testid="login-recover-link">
              ¿Olvidaste la contraseña?
            </button>
            <div className="border-t pt-4 mt-2" style={{ borderColor: 'var(--border)' }}>
              <p className="text-[10px] font-mono text-slate-500 leading-relaxed">
                Acceso restringido. Si no tenés credenciales, contactá al administrador de la planta.
              </p>
            </div>
          </form>
        ) : (
          <form onSubmit={doRecover} className="space-y-4" data-testid="recover-form">
            <h2 className="font-display text-sm font-medium text-amber-300 flex items-center gap-1.5"><Key size={14}/> Recuperar contraseña</h2>
            <p className="text-xs text-slate-400">Necesitás el código maestro guardado en <span className="font-mono text-amber-300/80">backend/.env</span> (ADMIN_RECOVERY_CODE).</p>
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">Usuario</label>
              <input data-testid="recover-username" value={username} onChange={e => setUsername(e.target.value)} className="field w-full" placeholder="admin" />
            </div>
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">Código maestro</label>
              <input data-testid="recover-code" value={recoveryCode} onChange={e => setRecoveryCode(e.target.value)} className="field w-full" placeholder="ADMIN_RECOVERY_CODE" />
            </div>
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">Nueva contraseña</label>
              <input data-testid="recover-newpwd" type="password" value={newPwd} onChange={e => setNewPwd(e.target.value)} className="field w-full" />
            </div>
            {error && <div className="text-xs font-mono text-red-400 border-l-2 border-red-500/40 pl-2" data-testid="recover-error">{error}</div>}
            <div className="flex gap-2">
              <button type="button" onClick={() => setRecovery(false)} className="flex-1 border border-[#232A26] text-slate-300 hover:bg-[#1A1E1C] py-2 text-sm" data-testid="recover-cancel">Volver</button>
              <button type="submit" disabled={loading} className="flex-1 bg-amber-300/10 text-amber-300 border border-amber-300/30 hover:bg-amber-300/20 py-2 text-sm disabled:opacity-50" data-testid="recover-submit">
                {loading ? 'Procesando...' : 'Restablecer'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

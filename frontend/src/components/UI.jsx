import React from 'react';

export function StatusBadge({ state, label, testid }) {
  // state: 'online' | 'offline' | 'warning'
  const color = state === 'online' ? 'text-green-400 bg-green-500/10 border-green-500/30'
    : state === 'warning' ? 'text-amber-400 bg-amber-500/10 border-amber-500/30'
    : 'text-red-400 bg-red-500/10 border-red-500/30';
  const dotColor = state === 'online' ? 'text-green-400'
    : state === 'warning' ? 'text-amber-400'
    : 'text-red-400';
  return (
    <span
      data-testid={testid}
      className={`inline-flex items-center gap-2 px-2 py-1 text-[10px] font-mono uppercase tracking-wider border ${color}`}
    >
      <span className={`live-dot ${dotColor}`}>●</span>
      {label}
    </span>
  );
}

export function Card({ children, className = '', testid }) {
  return (
    <div data-testid={testid} className={`surface fade-in ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action, testid }) {
  return (
    <div data-testid={testid} className="flex items-start justify-between px-4 sm:px-6 pt-4 sm:pt-5 pb-3 border-b" style={{ borderColor: 'var(--border)' }}>
      <div>
        <h3 className="font-display text-base font-medium text-slate-100 tracking-tight">{title}</h3>
        {subtitle && <p className="font-mono text-[11px] text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Metric({ label, value, unit, color, big = false, testid }) {
  return (
    <div data-testid={testid} className="flex flex-col gap-1">
      <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">{label}</span>
      <div className="flex items-baseline gap-1.5">
        <span
          className={`font-mono font-light tracking-tight ${big ? 'text-3xl sm:text-4xl' : 'text-xl sm:text-2xl'}`}
          style={{ color: color || 'var(--text)' }}
        >
          {value}
        </span>
        {unit && <span className="font-mono text-xs text-slate-500">{unit}</span>}
      </div>
    </div>
  );
}

export function Btn({ children, onClick, variant = 'primary', testid, disabled }) {
  const styles = {
    primary: 'bg-slate-50 text-slate-900 hover:bg-slate-200',
    secondary: 'border border-[#232A26] bg-transparent text-slate-300 hover:bg-[#1A1E1C] hover:text-white',
    ai: 'bg-amber-300/10 text-amber-300 border border-amber-300/30 hover:bg-amber-300/20',
    danger: 'bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20',
  };
  return (
    <button
      data-testid={testid}
      onClick={onClick}
      disabled={disabled}
      className={`px-3 py-1.5 text-xs font-medium tracking-wide transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${styles[variant]}`}
    >
      {children}
    </button>
  );
}

export function Toggle({ value, onChange, label, testid }) {
  return (
    <label className="inline-flex items-center gap-2 cursor-pointer select-none" data-testid={`${testid}-label`}>
      <span
        data-testid={testid}
        role="switch"
        aria-checked={!!value}
        tabIndex={0}
        onClick={() => onChange(!value)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onChange(!value); } }}
        className={`toggle ${value ? 'on' : ''}`}
      />
      {label && <span className="text-xs text-slate-400 font-mono">{label}</span>}
    </label>
  );
}

export function Slider({ value, onChange, min = 0, max = 100, step = 1, label, unit = '', testid }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">{label}</span>
          <span className="font-mono text-sm text-slate-200">{value}{unit && <span className="text-slate-500 ml-1">{unit}</span>}</span>
        </div>
      )}
      <input
        data-testid={testid}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-green-400"
      />
    </div>
  );
}

export function NumberInput({ value, onChange, min, max, step = 1, label, unit, hint, testid, className = '' }) {
  return (
    <label className={`flex flex-col gap-1 ${className}`}>
      {label && <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">{label}{unit && <span className="text-slate-600 ml-1">({unit})</span>}</span>}
      <input
        data-testid={testid}
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value === '' ? '' : parseFloat(e.target.value))}
        className="field"
      />
      {hint && <span className="text-[10px] text-slate-500 mt-0.5 leading-tight">{hint}</span>}
    </label>
  );
}

export function TextInput({ value, onChange, label, testid, className = '', placeholder }) {
  return (
    <label className={`flex flex-col gap-1 ${className}`}>
      {label && <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">{label}</span>}
      <input
        data-testid={testid}
        type="text"
        value={value || ''}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="field"
      />
    </label>
  );
}

export function SectionTitle({ children, kicker }) {
  return (
    <div className="flex items-baseline gap-3 mb-3">
      {kicker && (
        <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">{kicker}</span>
      )}
      <h2 className="font-display text-lg font-medium text-slate-100">{children}</h2>
    </div>
  );
}

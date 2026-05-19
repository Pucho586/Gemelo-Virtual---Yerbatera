import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../lib/api';
import { X, BookOpen } from '@phosphor-icons/react';

export default function DocsModal({ onClose }) {
  const [list, setList] = useState([]);
  const [selected, setSelected] = useState(null);
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.docsList().then((l) => {
      setList(l || []);
      if (l && l.length > 0) loadDoc(l[0].name);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadDoc = (name) => {
    setLoading(true);
    setSelected(name);
    api.docsGet(name)
      .then((d) => setContent(d.content))
      .catch(() => setContent('Error cargando documento.'))
      .finally(() => setLoading(false));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-stretch bg-black/60 backdrop-blur-sm" data-testid="docs-modal" onClick={onClose}>
      <div
        className="m-auto bg-[#0E1411] border w-[95vw] h-[90vh] max-w-6xl flex flex-col"
        style={{ borderColor: 'var(--border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2 text-slate-100">
            <BookOpen size={18} className="text-amber-300" />
            <h2 className="font-display text-base font-medium">Documentación del sistema</h2>
          </div>
          <button onClick={onClose} data-testid="docs-close" className="text-slate-400 hover:text-slate-100">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 flex overflow-hidden">
          {/* Sidebar lista de docs */}
          <div className="w-64 border-r overflow-y-auto" style={{ borderColor: 'var(--border)' }}>
            {list.map((d) => (
              <button
                key={d.name}
                data-testid={`docs-item-${d.name}`}
                onClick={() => loadDoc(d.name)}
                className={`block w-full text-left px-4 py-3 border-b font-mono text-xs hover:bg-[#181F1B] transition-colors ${selected === d.name ? 'bg-amber-500/10 text-amber-300' : 'text-slate-300'}`}
                style={{ borderColor: 'var(--border)' }}
              >
                <div className="font-medium">{d.title}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">{d.name} · {(d.size / 1024).toFixed(1)} KB</div>
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-8 py-6">
            {loading ? (
              <div className="font-mono text-sm text-slate-500">Cargando...</div>
            ) : (
              <div className="docs-content prose prose-invert prose-sm max-w-none">
                <ReactMarkdown>{content}</ReactMarkdown>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

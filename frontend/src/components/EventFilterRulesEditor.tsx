import { useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { Plus, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import type { EventFilterRule } from '../services/api';

const MODE_LABEL: Record<EventFilterRule['mode'], string> = {
  contains: 'Contiene', wildcard: 'Comodín (*)', regex: 'Regex',
};
const FIELD_LABEL: Record<EventFilterRule['field'], string> = {
  message: 'Mensaje', topics: 'Temas', any: 'Mensaje o temas',
};

function Toggle({ value, onChange, c }: { value: boolean; onChange: (v: boolean) => void; c: any }) {
  return (
    <button type="button" onClick={() => onChange(!value)} className="relative w-10 h-5 rounded-full transition-colors" style={{ background: value ? c.green : c.border }}>
      <span className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full transition-transform bg-white" style={{ transform: value ? 'translateX(20px)' : 'translateX(0)' }} />
    </button>
  );
}

function RoleAssign({ value, options, onChange, c }: { value: string[]; options: { name: string }[]; onChange: (v: string[]) => void; c: any }) {
  const add = (name: string) => { if (name && !value.includes(name)) onChange([...value, name]); };
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {value.length === 0 && (
        <span className="text-[10px] px-1.5 py-0.5 rounded font-medium" style={{ background: c.greenBg, color: c.green }}>Todos (global)</span>
      )}
      {value.map(r => (
        <button type="button" key={r} onClick={() => onChange(value.filter(x => x !== r))} className="text-[10px] px-1.5 py-0.5 rounded font-medium flex items-center gap-1" style={{ background: c.accent, color: '#fff' }} title="Quitar rol">
          {r} ✕
        </button>
      ))}
      <select value="" onChange={e => { if (e.target.value) add(e.target.value); e.target.value = ''; }}
        className="text-[11px] rounded px-1 py-0.5" style={{ background: c.bgHover, color: c.textMuted, border: `1px solid ${c.border}` }}>
        <option value="">+ rol…</option>
        {options.filter(o => !value.includes(o.name)).map(o => (
          <option key={o.name} value={o.name}>{o.name}</option>
        ))}
      </select>
    </div>
  );
}

export default function EventFilterRulesEditor({
  value,
  onChange,
  helper,
  rolesOptions,
}: {
  value: EventFilterRule[];
  onChange: (next: EventFilterRule[]) => void;
  helper?: React.ReactNode;
  rolesOptions?: { name: string }[];
}) {
  const { c } = useTheme();
  const [draft, setDraft] = useState<{ name: string; pattern: string; mode: EventFilterRule['mode']; field: EventFilterRule['field']; roles: string[] }>({
    name: '', pattern: '', mode: 'wildcard', field: 'message', roles: [],
  });

  const addRule = () => {
    if (!draft.pattern.trim()) { toast.error('Ingresá un patrón'); return; }
    const rule: EventFilterRule = {
      id: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random())),
      name: draft.name.trim() || draft.pattern.trim(),
      pattern: draft.pattern.trim(),
      mode: draft.mode,
      field: draft.field,
      enabled: true,
      roles: draft.roles,
    };
    onChange([...value, rule]);
    setDraft({ name: '', pattern: '', mode: 'wildcard', field: 'message', roles: [] });
  };

  const updateRule = (id: string, patch: Partial<EventFilterRule>) =>
    onChange(value.map(f => f.id === id ? { ...f, ...patch } : f));

  const toggleEnabled = (id: string) => onChange(value.map(f => f.id === id ? { ...f, enabled: !f.enabled } : f));
  const remove = (id: string) => onChange(value.filter(f => f.id !== id));

  return (
    <div className="space-y-3">
      {helper && <div className="rounded-lg p-3 text-xs" style={{ background: c.bgHover, color: c.textMuted }}>{helper}</div>}

      <div className="card !p-4 space-y-3">
        <h3 className="text-sm font-semibold" style={{ color: c.textPrimary }}>Nueva regla</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Nombre</label>
            <input className="input w-full text-sm" value={draft.name} placeholder="ej: Logins API"
              onChange={e => setDraft({ ...draft, name: e.target.value })} />
          </div>
          <div>
            <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Patrón</label>
            <input className="input w-full text-sm font-mono" value={draft.pattern} placeholder="user * logged in from * via api"
              onChange={e => setDraft({ ...draft, pattern: e.target.value })} />
          </div>
          <div>
            <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Coincidencia</label>
            <select className="input w-full text-sm" value={draft.mode} onChange={e => setDraft({ ...draft, mode: e.target.value as EventFilterRule['mode'] })}>
              <option value="wildcard">Comodín (*)</option>
              <option value="contains">Contiene</option>
              <option value="regex">Expresión regular</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Aplicar a</label>
            <select className="input w-full text-sm" value={draft.field} onChange={e => setDraft({ ...draft, field: e.target.value as EventFilterRule['field'] })}>
              <option value="message">Mensaje</option>
              <option value="topics">Temas</option>
              <option value="any">Mensaje o temas</option>
            </select>
          </div>
        </div>
        {rolesOptions && (
          <div>
            <label className="text-[10px] uppercase font-medium block mb-1" style={{ color: c.textMuted }}>Roles afectados</label>
            <RoleAssign value={draft.roles} options={rolesOptions} onChange={roles => setDraft({ ...draft, roles })} c={c} />
          </div>
        )}
        <button type="button" onClick={addRule} className="btn-primary text-sm"><Plus className="w-4 h-4 inline mr-1" />Agregar regla</button>
      </div>

      <div className="space-y-2">
        {value.length === 0 && <p className="text-sm" style={{ color: c.textMuted }}>No hay reglas configuradas.</p>}
        {value.map(f => (
          <div key={f.id} className="card !p-3 flex items-center gap-3">
            <Toggle value={f.enabled} onChange={() => toggleEnabled(f.id)} c={c} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium" style={{ color: c.textPrimary }}>{f.name}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: c.bgHover, color: c.textMuted }}>{MODE_LABEL[f.mode]}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: c.bgHover, color: c.textMuted }}>{FIELD_LABEL[f.field]}</span>
              </div>
              <p className="text-[11px] font-mono truncate" style={{ color: c.textMuted }}>{f.pattern}</p>
              {rolesOptions && (
                <div className="mt-1.5">
                  <RoleAssign value={f.roles || []} options={rolesOptions} onChange={roles => updateRule(f.id, { roles })} c={c} />
                </div>
              )}
            </div>
            <button type="button" onClick={() => remove(f.id)} className="p-1.5 rounded" style={{ color: c.red }} title="Eliminar">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

import { useState, useEffect, useMemo } from 'react';
import { routersAPI, routerosAPI } from '../services/api';
import type { BulkCommandResult } from '../services/api';
import type { RouterDevice } from '../types';
import { useTheme } from '../contexts/ThemeContext';
import { Layers, Send, Search, CheckCircle2, XCircle, ChevronDown, ChevronRight } from 'lucide-react';
import toast from 'react-hot-toast';

export default function BulkCommandPage() {
  const { c } = useTheme();
  const [routers, setRouters] = useState<RouterDevice[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState('');
  const [onlineOnly, setOnlineOnly] = useState(true);
  const [command, setCommand] = useState('');
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<BulkCommandResult[]>([]);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  useEffect(() => { routersAPI.list().then(setRouters).catch(console.error); }, []);

  const filtered = useMemo(() => {
    const s = search.toLowerCase();
    return routers.filter(r =>
      (!onlineOnly || r.is_online) &&
      (!s || r.name.toLowerCase().includes(s) || r.ip_address.toLowerCase().includes(s))
    );
  }, [routers, search, onlineOnly]);

  const allVisibleSelected = filtered.length > 0 && filtered.every(r => selected.has(r.id));

  const toggle = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    setSelected(prev => {
      const next = new Set(prev);
      if (allVisibleSelected) filtered.forEach(r => next.delete(r.id));
      else filtered.forEach(r => next.add(r.id));
      return next;
    });
  };

  const toggleExpand = (id: number) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleRun = async () => {
    const ids = Array.from(selected);
    if (ids.length === 0) { toast.error('Seleccioná al menos un router'); return; }
    if (!command.trim()) { toast.error('Escribí un comando'); return; }
    if (!confirm(`¿Ejecutar el comando en ${ids.length} router(s)?\n\n${command}`)) return;
    setRunning(true);
    setResults([]);
    setExpanded(new Set());
    try {
      const res = await routerosAPI.bulkCommand(ids, command.trim());
      setResults(res.results);
      const ok = res.results.filter(r => r.success).length;
      toast.success(`Ejecutado: ${ok}/${res.results.length} con éxito`);
    } catch (err: any) {
      toast.error(err.message || 'Error al ejecutar');
    } finally {
      setRunning(false);
    }
  };

  const okCount = results.filter(r => r.success).length;
  const failCount = results.length - okCount;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: c.textPrimary }}>
        <Layers className="w-6 h-6" />Comandos en Lote
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold" style={{ color: c.textPrimary }}>
              Routers <span style={{ color: c.textMuted }}>({selected.size} seleccionados)</span>
            </h3>
            <label className="flex items-center gap-1.5 text-xs cursor-pointer" style={{ color: c.textMuted }}>
              <input type="checkbox" checked={onlineOnly} onChange={e => setOnlineOnly(e.target.checked)} />
              Solo en línea
            </label>
          </div>
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: c.textMuted }} />
            <input type="text" className="input pl-9 py-1.5 text-sm" placeholder="Buscar router..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <div className="rounded-lg overflow-hidden" style={{ border: `1px solid ${c.border}` }}>
            <div className="flex items-center gap-2 px-3 py-2" style={{ borderBottom: `1px solid ${c.border}`, background: c.bgHover }}>
              <input type="checkbox" checked={allVisibleSelected} onChange={toggleAll} />
              <span className="text-xs font-medium" style={{ color: c.textMuted }}>Seleccionar todos ({filtered.length})</span>
            </div>
            <div className="max-h-[360px] overflow-y-auto">
              {filtered.length === 0 && (
                <div className="text-center py-8 text-sm" style={{ color: c.textMuted }}>No hay routers</div>
              )}
              {filtered.map(r => (
                <label key={r.id} className="flex items-center gap-2 px-3 py-2 cursor-pointer" style={{ borderBottom: `1px solid ${c.border}` }}>
                  <input type="checkbox" checked={selected.has(r.id)} onChange={() => toggle(r.id)} />
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: r.is_online ? c.green : c.red }} />
                  <span className="text-sm font-medium truncate" style={{ color: c.textPrimary }}>{r.name}</span>
                  <span className="text-xs ml-auto shrink-0" style={{ color: c.textMuted }}>{r.ip_address}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="card flex flex-col">
          <h3 className="text-sm font-semibold mb-3" style={{ color: c.textPrimary }}>Comando RouterOS</h3>
          <textarea
            className="input font-mono text-sm flex-1"
            rows={6}
            placeholder="/system/identity/print&#10;/ip/dns/set servers=1.1.1.1"
            value={command}
            onChange={e => setCommand(e.target.value)}
          />
          <div className="mt-3 flex items-center gap-2 text-xs" style={{ color: c.textMuted }}>
            <span>Un comando por ejecución. Se aplica a todos los routers seleccionados.</span>
          </div>
          <div className="mt-3 flex justify-end">
            <button onClick={handleRun} disabled={running || selected.size === 0 || !command.trim()} className="btn-primary disabled:opacity-50">
              <Send className="w-4 h-4 inline mr-2" />{running ? 'Ejecutando...' : `Ejecutar en ${selected.size}`}
            </button>
          </div>
        </div>
      </div>

      {results.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-4 mb-3">
            <h3 className="text-sm font-semibold" style={{ color: c.textPrimary }}>Resultados</h3>
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: c.greenBg, color: c.green }}>{okCount} éxito</span>
            {failCount > 0 && <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: c.redBg, color: c.red }}>{failCount} error</span>}
          </div>
          <div className="rounded-lg overflow-hidden" style={{ border: `1px solid ${c.border}` }}>
            {results.map(r => {
              const isOpen = expanded.has(r.router_id);
              const text = r.success ? r.output : (r.error || 'Error');
              return (
                <div key={r.router_id} style={{ borderBottom: `1px solid ${c.border}` }}>
                  <button onClick={() => toggleExpand(r.router_id)} className="w-full flex items-center gap-2 px-3 py-2 text-left">
                    {isOpen ? <ChevronDown className="w-4 h-4" style={{ color: c.textMuted }} /> : <ChevronRight className="w-4 h-4" style={{ color: c.textMuted }} />}
                    {r.success ? <CheckCircle2 className="w-4 h-4 shrink-0" style={{ color: c.green }} /> : <XCircle className="w-4 h-4 shrink-0" style={{ color: c.red }} />}
                    <span className="text-sm font-medium" style={{ color: c.textPrimary }}>{r.router_name}</span>
                    {!r.success && <span className="text-xs truncate ml-2" style={{ color: c.red }}>{r.error}</span>}
                  </button>
                  {isOpen && (
                    <pre className="px-3 pb-3 pl-9 text-xs whitespace-pre-wrap font-mono" style={{ color: r.success ? c.textSecondary : c.red }}>{text || '(sin salida)'}</pre>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

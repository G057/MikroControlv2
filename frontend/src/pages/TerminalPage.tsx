import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { routersAPI, routerosAPI } from '../services/api';
import type { RouterDevice } from '../types';
import { useTheme } from '../contexts/ThemeContext';
import { Terminal as TerminalIcon, Send } from 'lucide-react';

interface TerminalLine {
  type: 'command' | 'output' | 'error' | 'info';
  text: string;
  timestamp: Date;
}

export default function TerminalPage() {
  const [searchParams] = useSearchParams();
  const [routers, setRouters] = useState<RouterDevice[]>([]);
  const [selectedRouter, setSelectedRouter] = useState<number>(Number(searchParams.get('router')) || 0);
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [command, setCommand] = useState('');
  const [history, setHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const [loading, setLoading] = useState(false);
  const termRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { c } = useTheme();

  useEffect(() => { routersAPI.list().then(setRouters).catch(console.error); }, []);
  useEffect(() => { if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight; }, [lines]);

  const addLine = (type: TerminalLine['type'], text: string) => {
    setLines(prev => [...prev, { type, text, timestamp: new Date() }]);
  };

  const handleSend = async () => {
    if (!command.trim() || !selectedRouter) return;
    const cmd = command.trim();
    addLine('command', `[${routers.find(r => r.id === selectedRouter)?.name || selectedRouter}] > ${cmd}`);
    setHistory(prev => [...prev, cmd]);
    setHistoryIdx(-1);
    setCommand('');
    setLoading(true);
    try {
      const result = await routerosAPI.command(selectedRouter, cmd);
      if (result.success) {
        if (result.output) result.output.split('\n').forEach((line: string) => { if (line.trim()) addLine('output', line); });
      } else addLine('error', result.error || 'Error al ejecutar comando');
    } catch (err: any) { addLine('error', err.message || 'Error de conexión'); }
    finally { setLoading(false); inputRef.current?.focus(); }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSend();
    else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (history.length > 0) {
        const newIdx = historyIdx < history.length - 1 ? historyIdx + 1 : historyIdx;
        setHistoryIdx(newIdx);
        setCommand(history[history.length - 1 - newIdx] || '');
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIdx > 0) { setHistoryIdx(historyIdx - 1); setCommand(history[history.length - 1 - (historyIdx - 1)] || ''); }
      else { setHistoryIdx(-1); setCommand(''); }
    }
  };

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: c.textPrimary }}>
          <TerminalIcon className="w-6 h-6" />Terminal RouterOS
        </h1>
        <select className="input w-auto" value={selectedRouter} onChange={(e) => {
          setSelectedRouter(Number(e.target.value)); setLines([]);
          if (e.target.value) addLine('info', `Conectado a router #${e.target.value}`);
        }}>
          <option value={0}>Seleccionar router...</option>
          {routers.filter(r => r.is_online).map(r => <option key={r.id} value={r.id}>{r.name} ({r.ip_address})</option>)}
        </select>
      </div>

      <div ref={termRef} className="flex-1 rounded-xl p-4 overflow-y-auto font-mono text-sm min-h-[400px] max-h-[calc(100vh-280px)]"
        style={{ background: '#0d1117', border: `1px solid ${c.border}` }} onClick={() => inputRef.current?.focus()}>
        {lines.length === 0 && (
          <div style={{ color: c.textMuted }}>
            MikroControl Terminal v1.0<br />
            Seleccioná un router y escribí un comando RouterOS.<br /><br />
          </div>
        )}
        {lines.map((line, i) => (
          <div key={i} className="whitespace-pre-wrap" style={{
            color: line.type === 'command' ? c.textLink : line.type === 'error' ? c.red : line.type === 'info' ? c.yellow : c.green,
            fontWeight: line.type === 'command' ? 700 : 400,
          }}>
            {line.text}
          </div>
        ))}
        {loading && <div className="animate-pulse" style={{ color: c.textMuted }}>Ejecutando...</div>}
      </div>

      <div className="flex gap-2">
        <div className="flex-1 relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 font-mono text-sm" style={{ color: c.textLink }}>$</span>
          <input ref={inputRef} className="input pl-8 font-mono"
            placeholder={selectedRouter ? "Escribí un comando RouterOS..." : "Seleccioná un router primero"}
            value={command} onChange={(e) => setCommand(e.target.value)} onKeyDown={handleKeyDown}
            disabled={!selectedRouter || loading} autoFocus />
        </div>
        <button onClick={handleSend} className="btn-primary" disabled={!selectedRouter || loading || !command.trim()}>
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

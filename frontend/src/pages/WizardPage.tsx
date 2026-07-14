import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import { routersAPI, routerosAPI } from '../services/api';
import type { RouterDevice } from '../types';
import {
  Wifi, WifiOff, Globe, Settings, Check, AlertTriangle,
  Loader2, Save, ArrowLeft, ArrowRight, Radio, Server
} from 'lucide-react';

export default function WizardPage() {
  const { c } = useTheme();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [routers, setRouters] = useState<RouterDevice[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [wanConfig, setWanConfig] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [loadingRouters, setLoadingRouters] = useState(true);
  const [step, setStep] = useState(1);

  const [wanInterface, setWanInterface] = useState('');
  const [wanType, setWanType] = useState<'dhcp' | 'pppoe' | 'static'>('dhcp');
  const [pppoeUser, setPppoeUser] = useState('');
  const [pppoePass, setPppoePass] = useState('');
  const [staticIp, setStaticIp] = useState('');
  const [staticGw, setStaticGw] = useState('');
  const [staticDns, setStaticDns] = useState('');
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    routersAPI.list().then(data => {
      setRouters(data);
      setLoadingRouters(false);
    }).catch(() => setLoadingRouters(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    setStep(1);
    setWanConfig(null);
    setResult(null);
    routerosAPI.wanConfig(selectedId).then(data => {
      setWanConfig(data);
      setLoading(false);
      const running = data.interfaces.find(i => i.running && i.type === 'ether');
      if (running) setWanInterface(running.name);
      if (data.pppoe_clients.length > 0) {
        setWanType('pppoe');
        setPppoeUser(data.pppoe_clients[0].user || '');
      } else if (data.dhcp_clients.length > 0) {
        setWanType('dhcp');
      } else if (data.addresses.length > 0) {
        setWanType('static');
        const wanAddr = data.addresses.find((a: any) => a.interface === wanInterface);
        if (wanAddr) setStaticIp(wanAddr.address);
        if (data.gateway) setStaticGw(data.gateway);
        if (data.dns_servers) setStaticDns(data.dns_servers);
      }
    }).catch(() => { setLoading(false); setResult({ success: false, message: 'Error al cargar configuración WAN' }); });
  }, [selectedId]);

  const selectedRouter = routers.find(r => r.id === selectedId);

  const handleApply = async () => {
    if (!selectedId) return;
    setApplying(true);
    setResult(null);
    try {
      const res = await routerosAPI.configureWan({
        router_id: selectedId,
        wan_interface: wanInterface,
        wan_type: wanType,
        pppoe_user: wanType === 'pppoe' ? pppoeUser : undefined,
        pppoe_password: wanType === 'pppoe' ? pppoePass : undefined,
        ip_address: wanType === 'static' ? staticIp : undefined,
        gateway: wanType === 'static' ? staticGw : undefined,
        dns_servers: wanType === 'static' ? staticDns : undefined,
      });
      setResult({ success: res.success, message: res.message || res.error || 'Error desconocido' });
      if (res.success) setStep(3);
    } catch (e: any) {
      setResult({ success: false, message: e.message || 'Error de conexión' });
    }
    setApplying(false);
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-6" style={{ color: c.textPrimary }}>
      <h1 className="text-xl font-bold mb-6 flex items-center gap-2">
        <Settings className="w-6 h-6" style={{ color: c.accent }} />
        Configurador WAN
      </h1>

      {/* Selector de router */}
      <div className="rounded-xl p-4 mb-4" style={{ background: c.bgCard, border: `1px solid ${c.borderLight}` }}>
        <label className="text-sm font-medium mb-2 block" style={{ color: c.textSecondary }}>Router</label>
        {loadingRouters ? (
          <Loader2 className="w-5 h-5 animate-spin" style={{ color: c.textMuted }} />
        ) : (
          <select
            value={selectedId || ''}
            onChange={e => setSelectedId(Number(e.target.value) || null)}
            className="w-full rounded-lg px-3 py-2 text-sm outline-none"
            style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }}
          >
            <option value="">Seleccionar router...</option>
            {routers.map(r => (
              <option key={r.id} value={r.id}>
                {r.name} {r.is_online ? '' : '(offline)'}
              </option>
            ))}
          </select>
        )}
      </div>

      {loading && (
        <div className="flex items-center gap-2 py-8 justify-center" style={{ color: c.textMuted }}>
          <Loader2 className="w-5 h-5 animate-spin" /> Cargando configuración actual...
        </div>
      )}

      {wanConfig && !loading && (
        <>
          {/* Config actual */}
          <div className="rounded-xl p-4 mb-4" style={{ background: c.bgCard, border: `1px solid ${c.borderLight}` }}>
            <h2 className="text-sm font-semibold mb-3" style={{ color: c.textSecondary }}>Configuración actual</h2>
            <div className="text-xs space-y-2" style={{ color: c.textMuted }}>
              <div><span className="font-medium">Interfaces WAN:</span> {wanConfig.interfaces.map((i: any) => i.name).join(', ') || 'Ninguna'}</div>
              <div><span className="font-medium">IPs:</span> {wanConfig.addresses.map((a: any) => `${a.interface}: ${a.address}`).join(', ') || 'Ninguna'}</div>
              <div><span className="font-medium">DHCP:</span> {wanConfig.dhcp_clients.map((d: any) => `${d.interface} (${d.status})`).join(', ') || 'Ninguno'}</div>
              <div><span className="font-medium">PPPoE:</span> {wanConfig.pppoe_clients.map((p: any) => `${p.name} (${p.user})`).join(', ') || 'Ninguno'}</div>
              <div><span className="font-medium">Gateway:</span> {wanConfig.gateway || 'Ninguno'}</div>
              <div><span className="font-medium">DNS:</span> {wanConfig.dns_servers || 'Ninguno'}</div>
            </div>
          </div>

          {/* Formulario de configuración */}
          <div className="rounded-xl p-4 mb-4" style={{ background: c.bgCard, border: `1px solid ${c.borderLight}` }}>
            <h2 className="text-sm font-semibold mb-3" style={{ color: c.textSecondary }}>Nueva configuración</h2>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Interfaz WAN</label>
                <select
                  value={wanInterface}
                  onChange={e => setWanInterface(e.target.value)}
                  className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                  style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }}
                >
                  <option value="">Seleccionar interfaz...</option>
                  {wanConfig.interfaces.map((i: any) => (
                    <option key={i.name} value={i.name}>{i.name} ({i.type}) {i.running ? '✓' : '✗'}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Tipo de conexión WAN</label>
                <div className="flex gap-2">
                  {(['dhcp', 'pppoe', 'static'] as const).map(t => (
                    <button
                      key={t}
                      onClick={() => setWanType(t)}
                      className="flex-1 py-2 rounded-lg text-sm font-medium transition-colors"
                      style={{
                        background: wanType === t ? c.accent : c.bgHover,
                        color: wanType === t ? '#fff' : c.textSecondary,
                        border: `1px solid ${wanType === t ? c.accent : c.border}`,
                      }}
                    >
                      {t === 'dhcp' ? 'DHCP' : t === 'pppoe' ? 'PPPoE' : 'IP Fija'}
                    </button>
                  ))}
                </div>
              </div>

              {wanType === 'pppoe' && (
                <>
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Usuario PPPoE</label>
                    <input value={pppoeUser} onChange={e => setPppoeUser(e.target.value)}
                      className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                      style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }}
                      placeholder="usuario@isp" />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Contraseña PPPoE</label>
                    <input type="password" value={pppoePass} onChange={e => setPppoePass(e.target.value)}
                      className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                      style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }}
                      placeholder="contraseña" />
                  </div>
                </>
              )}

              {wanType === 'static' && (
                <>
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Dirección IP (ej: 192.168.1.2/24)</label>
                    <input value={staticIp} onChange={e => setStaticIp(e.target.value)}
                      className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                      style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }}
                      placeholder="192.168.1.2/24" />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>Gateway</label>
                    <input value={staticGw} onChange={e => setStaticGw(e.target.value)}
                      className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                      style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }}
                      placeholder="192.168.1.1" />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: c.textSecondary }}>DNS (separados por coma)</label>
                    <input value={staticDns} onChange={e => setStaticDns(e.target.value)}
                      className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                      style={{ background: c.bgInput, color: c.textPrimary, border: `1px solid ${c.border}` }}
                      placeholder="8.8.8.8,1.1.1.1" />
                  </div>
                </>
              )}
            </div>

            <button
              onClick={handleApply}
              disabled={applying || !wanInterface}
              className="w-full mt-4 py-2.5 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-2"
              style={{
                background: c.accent,
                color: '#fff',
                opacity: applying || !wanInterface ? 0.6 : 1,
              }}
            >
              {applying ? <><Loader2 className="w-4 h-4 animate-spin" /> Aplicando...</> : <><Save className="w-4 h-4" /> Aplicar configuración WAN</>}
            </button>
          </div>

          {result && (
            <div className="rounded-xl p-4 flex items-start gap-3" style={{
              background: result.success ? 'rgba(74,222,128,0.1)' : 'rgba(248,113,113,0.1)',
              border: `1px solid ${result.success ? 'rgba(74,222,128,0.3)' : 'rgba(248,113,113,0.3)'}`,
            }}>
              {result.success ? <Check className="w-5 h-5 flex-shrink-0" style={{ color: c.green }} /> : <AlertTriangle className="w-5 h-5 flex-shrink-0" style={{ color: c.red }} />}
              <div>
                <p className="text-sm font-medium" style={{ color: result.success ? c.green : c.red }}>{result.success ? 'Configuración aplicada' : 'Error'}</p>
                <p className="text-xs mt-1" style={{ color: c.textMuted }}>{result.message}</p>
              </div>
            </div>
          )}
        </>
      )}

      {!selectedId && !loadingRouters && (
        <div className="flex flex-col items-center justify-center py-16" style={{ color: c.textMuted }}>
          <Globe className="w-12 h-12 mb-3 opacity-40" />
          <p className="text-sm">Seleccioná un router para ver y configurar su WAN</p>
        </div>
      )}
    </div>
  );
}

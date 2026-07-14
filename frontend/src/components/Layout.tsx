import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { ROUTER_VIEW_PERMS } from '../types';
import { useTheme } from '../contexts/ThemeContext';
import {
  LayoutDashboard, Server, Users, Bell,
  HardDrive, ClipboardList, Terminal, LogOut, Shield, Menu, X, Network,
  Sun, Moon, Settings, Layers, Radio
} from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import { alertsAPI, logoAPI, versionAPI } from '../services/api';
import { nowArgentina } from '../utils/date';

type NavItem = { to: string; icon: any; label: string; permission: string | string[] };
type NavNode = NavItem | { subheader: string };

const navGroups: { label?: string; items: NavNode[] }[] = [
  {
    items: [
      { to: '/', icon: LayoutDashboard, label: 'Dashboard', permission: 'dashboard:view' },
      { to: '/monitor', icon: Radio, label: 'Monitor', permission: 'monitor:view' },
      { to: '/routers', icon: Server, label: 'Routers', permission: ROUTER_VIEW_PERMS },
      { to: '/groups', icon: Network, label: 'Grupos', permission: 'groups:view' },
      { to: '/terminal', icon: Terminal, label: 'Terminal', permission: 'routers:terminal' },
      { to: '/bulk-command', icon: Layers, label: 'Comandos en Lote', permission: 'routers:bulk_command' },
      { to: '/backups', icon: HardDrive, label: 'Backups', permission: 'routers:backup' },
      { to: '/events', icon: Bell, label: 'Eventos', permission: 'events:view' },
      { to: '/audit', icon: ClipboardList, label: 'Auditoría', permission: 'audit:view' },
    ],
  },
  {
    label: 'Sistema',
    items: [
      { to: '/settings', icon: Settings, label: 'Configuración', permission: 'settings:view' },
      { subheader: 'Administración de permisos' },
      { to: '/users', icon: Users, label: 'Usuarios', permission: 'users:view' },
      { to: '/roles', icon: Shield, label: 'Roles y Permisos', permission: 'roles:manage' },
    ],
  },
];

const ROLE_LABELS: Record<string, string> = {
  admin: 'Administrador', supervisor: 'Supervisor',
  tecnico_n2: 'Técnico N2', tecnico_n1: 'Técnico N1', tecnico_n3: 'Técnico N3', auditor: 'Auditor',
};

export default function Layout() {
  const { user, logout, hasPermission, hasAnyPermission } = useAuth();
  const { toggle, isDark, c } = useTheme();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [alertCount, setAlertCount] = useState(0);
  const [prevCritical, setPrevCritical] = useState(0);
  const [appVersion, setAppVersion] = useState('');

  const showToast = async (msg: string) => {
    const { toast } = await import('react-hot-toast');
    toast.error(msg, { id: 'critical-alert' });
  };

  const fetchAlertCount = useCallback(async () => {
    try {
      const data = await alertsAPI.unresolvedCount();
      const newCritical = data.critical || 0;
      if (prevCritical > 0 && newCritical > prevCritical) {
        showToast(`Alertas críticas: ${newCritical} activas`);
      }
      setPrevCritical(newCritical);
      setAlertCount(data.total || 0);
    } catch {}
  }, [prevCritical]);

  useEffect(() => {
    fetchAlertCount();
    const iv = setInterval(fetchAlertCount, 15000);
    return () => clearInterval(iv);
  }, [fetchAlertCount]);

  useEffect(() => {
    versionAPI.get().then((v) => setAppVersion(`v${v.version}${v.edition ? ' · ' + v.edition : ''}`)).catch(() => {});
  }, []);

  const handleLogout = () => { logout(); navigate('/login'); };

  return (
    <div className="h-screen flex overflow-hidden" style={{ background: c.bgPage, color: c.textPrimary }}>
      {sidebarOpen && (
        <div className="fixed inset-0 z-30 lg:hidden" style={{ background: c.bgOverlay }} onClick={() => setSidebarOpen(false)} />
      )}

      <aside
        className={`fixed lg:static lg:h-screen inset-y-0 left-0 z-40 w-64 flex flex-col transform transition-transform duration-200 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
        style={{ background: c.bgSidebar, borderRight: `1px solid ${c.border}` }}
      >
        <div className="p-4" style={{ borderBottom: `1px solid ${c.border}` }}>
          <a href="/" className="block">
            <img src={logoAPI.url()} alt="MikroControl" className="h-10 w-auto" />
          </a>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navGroups.map((group, gi) => {
            const canSee = (p: string | string[]) => Array.isArray(p) ? hasAnyPermission(p) : hasPermission(p);
            const visibleItems = group.items.filter((it): it is NavItem => !('subheader' in it) && canSee(it.permission));
            if (group.label && visibleItems.length === 0) return null;
            const hasPermItems = group.items.some((it): it is NavItem => !('subheader' in it) && canSee(it.permission));
            return (
              <div key={gi} className="space-y-1">
                {group.label && (
                  <div className="px-3 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider" style={{ color: c.textMuted }}>
                    {group.label}
                  </div>
                )}
                {group.items.map((item, ii) => {
                  if ('subheader' in item) {
                    if (!hasPermItems) return null;
                    return (
                      <div key={ii} className="px-3 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider" style={{ color: c.textMuted }}>
                        {item.subheader}
                      </div>
                    );
                  }
                  if (!canSee(item.permission)) return null;
                  return (
                    <NavLink
                      key={item.to} to={item.to} end={item.to === '/'}
                      className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
                      onClick={() => setSidebarOpen(false)}
                    >
                      <item.icon className="w-4 h-4" />
                      {item.label}
                      {item.to === '/events' && alertCount > 0 && (
                        <span className="ml-auto px-1.5 py-0.5 rounded-full text-xs text-white font-bold min-w-[20px] text-center" style={{ background: c.red }}>
                          {alertCount > 99 ? '99+' : alertCount}
                        </span>
                      )}
                    </NavLink>
                  );
                })}
              </div>
            );
          })}
        </nav>

        <div className="p-4" style={{ borderTop: `1px solid ${c.border}` }}>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: c.bgHover }}>
              <Shield className="w-4 h-4" style={{ color: c.textMuted }} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate" style={{ color: c.textPrimary }}>{user?.full_name}</p>
              <p className="text-xs" style={{ color: c.textMuted }}>{ROLE_LABELS[user?.role || ''] || (user?.role ? user.role.charAt(0).toUpperCase() + user.role.slice(1) : '')}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="sidebar-link w-full" style={{ color: c.red }}>
            <LogOut className="w-4 h-4" />
            Cerrar Sesión
          </button>
          {appVersion && (
            <p className="text-xs text-center mt-3 select-text" style={{ color: c.textMuted }}>
              {appVersion}
            </p>
          )}
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 flex items-center justify-between px-6" style={{ background: c.accent }}>
          <div className="flex items-center gap-3">
            <button className="lg:hidden text-white hover:text-white/90" onClick={() => setSidebarOpen(!sidebarOpen)}>
              {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
            <img src={logoAPI.url()} alt="MikroControl" className="h-8 w-auto lg:hidden" />
          </div>
          <div className="flex items-center gap-3">
            <button onClick={toggle} className="p-2 text-white hover:text-white/90 rounded-lg hover:bg-white/15 transition-colors" title={isDark ? 'Modo día' : 'Modo noche'}>
              {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
            <button onClick={() => navigate('/events')} className="relative p-2 text-white hover:text-white/90 rounded-lg hover:bg-white/15 transition-colors" title="Eventos">
              <Bell className="w-5 h-5" />
              {alertCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 px-1.5 py-0.5 rounded-full text-[10px] text-white font-bold min-w-[18px] text-center leading-none" style={{ background: c.red }}>
                  {alertCount > 99 ? '99+' : alertCount}
                </span>
              )}
            </button>
            <span className="text-xs text-white/90">{nowArgentina()}</span>
          </div>
        </header>
        <main className="flex-1 p-6 overflow-auto"><Outlet /></main>
      </div>
    </div>
  );
}

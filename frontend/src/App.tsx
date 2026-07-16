import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { ROUTER_VIEW_PERMS } from './types';
import ErrorBoundary from './components/ErrorBoundary';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import RoutersPage from './pages/RoutersPage';
import RouterDetailPage from './pages/RouterDetailPage';
import UsersPage from './pages/UsersPage';
import GroupsPage from './pages/GroupsPage';
import AlertsPage from './pages/AlertsPage';
import BackupsPage from './pages/BackupsPage';
import AuditPage from './pages/AuditPage';
import TerminalPage from './pages/TerminalPage';
import BulkCommandPage from './pages/BulkCommandPage';
import SystemSettingsPage from './pages/SystemSettingsPage';
import RolesPage from './pages/RolesPage';
import MonitorPage from './pages/MonitorPage';
import WizardPage from './pages/WizardPage';
const EventExplorerPage = lazy(() => import('./pages/EventExplorerPage'));
const EventReportPage = lazy(() => import('./pages/EventReportPage'));

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--bg-page)' }}>
        <div style={{ color: 'var(--text-muted)' }}>Cargando...</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AccessDenied() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Acceso denegado</div>
      <div className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
        No tenés permiso para ver esta sección.
      </div>
    </div>
  );
}

function RequirePermission({ permission, children }: { permission: string; children: React.ReactNode }) {
  const { hasPermission } = useAuth();
  if (!hasPermission(permission)) return <AccessDenied />;
  return <>{children}</>;
}

function DashboardOrMonitor() {
  const { hasPermission } = useAuth();
  if (hasPermission('dashboard:view')) return <DashboardPage />;
  if (hasPermission('monitor:view')) return <Navigate to="/monitor" replace />;
  return <AccessDenied />;
}

function RequireAnyPermission({ permissions, children }: { permissions: string[]; children: React.ReactNode }) {
  const { hasAnyPermission } = useAuth();
  if (!hasAnyPermission(permissions)) return <AccessDenied />;
  return <>{children}</>;
}

function AppRoutes() {
  const { user } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/monitor" element={<ProtectedRoute><RequirePermission permission="monitor:view"><MonitorPage /></RequirePermission></ProtectedRoute>} />
      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<DashboardOrMonitor />} />
        <Route path="routers" element={<RequireAnyPermission permissions={ROUTER_VIEW_PERMS}><RoutersPage /></RequireAnyPermission>} />
        <Route path="routers/:id" element={<RequireAnyPermission permissions={ROUTER_VIEW_PERMS}><RouterDetailPage /></RequireAnyPermission>} />
        <Route path="groups" element={<RequirePermission permission="groups:view"><GroupsPage /></RequirePermission>} />
        <Route path="users" element={<RequirePermission permission="users:view"><UsersPage /></RequirePermission>} />
        <Route path="roles" element={<RequirePermission permission="roles:manage"><RolesPage /></RequirePermission>} />
        <Route path="events" element={<RequirePermission permission="events:view"><AlertsPage /></RequirePermission>} />
        <Route path="events/explorer" element={<RequirePermission permission="events:view"><Suspense fallback={<div>Cargando explorador...</div>}><EventExplorerPage /></Suspense></RequirePermission>} />
        <Route path="events/report" element={<RequirePermission permission="events:view"><Suspense fallback={<div>Cargando informes...</div>}><EventReportPage /></Suspense></RequirePermission>} />
        <Route path="backups" element={<RequirePermission permission="routers:backup"><BackupsPage /></RequirePermission>} />
        <Route path="audit" element={<RequirePermission permission="audit:view"><AuditPage /></RequirePermission>} />
        <Route path="terminal" element={<RequirePermission permission="routers:terminal"><TerminalPage /></RequirePermission>} />
        <Route path="bulk-command" element={<RequirePermission permission="routers:bulk_command"><BulkCommandPage /></RequirePermission>} />
        <Route path="settings" element={<RequirePermission permission="settings:view"><SystemSettingsPage /></RequirePermission>} />
        <Route path="wizard" element={<RequirePermission permission="routers:configure_wan"><WizardPage /></RequirePermission>} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <AppRoutes />
            <Toaster
              position="top-right"
              toastOptions={{
                style: {
                  background: '#1e293b',
                  color: '#e2e8f0',
                  border: '1px solid #334155',
                },
              }}
            />
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

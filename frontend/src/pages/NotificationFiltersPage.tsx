import { useTheme } from '../contexts/ThemeContext';
import { EventFiltersTab } from './SystemSettingsPage';

export default function NotificationFiltersPage() {
  const { c } = useTheme();
  return <div className="space-y-5"><div><h1 className="text-2xl font-bold" style={{ color: c.textPrimary }}>Filtros de Notificación</h1><p className="text-sm" style={{ color: c.textMuted }}>Configurá por separado qué se oculta del historial, qué no muestra popup y qué no llega a Telegram.</p></div><div className="card !p-5"><EventFiltersTab c={c} /></div></div>;
}

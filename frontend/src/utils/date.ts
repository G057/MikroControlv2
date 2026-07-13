let _tz = localStorage.getItem('mk_tz') || 'America/Argentina/Buenos_Aires';

export function setTimezone(tz: string) {
  _tz = tz;
  localStorage.setItem('mk_tz', tz);
}

export function getTimezone(): string {
  return _tz;
}

export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return '';
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString('es-AR', { timeZone: _tz, year: 'numeric', month: '2-digit', day: '2-digit' });
}

export function formatDateTime(date: string | Date | null | undefined): string {
  if (!date) return '';
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleString('es-AR', {
    timeZone: _tz,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  });
}

export function formatTime(date: string | Date | null | undefined): string {
  if (!date) return '';
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleTimeString('es-AR', { timeZone: _tz, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

export function nowArgentina(): string {
  return new Date().toLocaleString('es-AR', {
    timeZone: _tz,
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
}

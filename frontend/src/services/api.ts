import type { User, RouterDevice, RouterGroup, RouterTag, DashboardData, DashboardCharts, AuditLogEntry, InventoryItem, Alert, AlertRule, ConfigTemplate, Backup, MonitorRouter, MonitorResponse } from '../types';

const API_BASE = '/api/v1';
const REQUEST_TIMEOUT_MS = 15_000;

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('mc_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers, signal: controller.signal });
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw new Error('La solicitud excedió 15 segundos');
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }

  if (response.status === 401) {
    localStorage.removeItem('mc_token');
    localStorage.removeItem('mc_user');
    window.location.href = '/login';
    throw new Error('No autorizado');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || 'Error en la petición');
  }

  return response.json();
}

// Auth
export const authAPI = {
  login: (username: string, password: string) =>
    request<{ access_token: string; user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  me: () => request<User>('/auth/me'),
  logout: () => request<{ detail: string }>('/auth/logout', { method: 'POST' }),
};

// Version
export const versionAPI = {
  get: () => request<{ name: string; version: string; edition: string }>('/version'),
};

// Routers
export const routersAPI = {
  list: (params?: { group_id?: number; search?: string; is_online?: boolean }) => {
    const query = new URLSearchParams();
    if (params?.group_id) query.set('group_id', String(params.group_id));
    if (params?.search) query.set('search', params.search);
    if (params?.is_online !== undefined) query.set('is_online', String(params.is_online));
    const qs = query.toString();
    return request<RouterDevice[]>(`/routers/${qs ? '?' + qs : ''}`);
  },
  get: (id: number) => request<RouterDevice>(`/routers/${id}`),
  create: (data: Partial<RouterDevice> & { api_password?: string }) =>
    request<RouterDevice>('/routers/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: Partial<RouterDevice>) =>
    request<RouterDevice>(`/routers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: number) => request(`/routers/${id}`, { method: 'DELETE' }),
  check: (id: number) => request(`/routers/${id}/check`, { method: 'POST' }),
};

// Groups
export const groupsAPI = {
  list: () => request<RouterGroup[]>('/groups/'),
  create: (data: Partial<RouterGroup>) =>
    request<RouterGroup>('/groups/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: Partial<RouterGroup>) =>
    request<RouterGroup>(`/groups/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: number) => request(`/groups/${id}`, { method: 'DELETE' }),
  listTags: () => request<RouterTag[]>('/groups/tags/'),
  createTag: (data: Partial<RouterTag>) =>
    request<RouterTag>('/groups/tags/', { method: 'POST', body: JSON.stringify(data) }),
  deleteTag: (id: number) => request(`/groups/tags/${id}`, { method: 'DELETE' }),
};

// Dashboard
export const dashboardAPI = {
  get: () => request<DashboardData>('/dashboard/'),
  charts: () => request<DashboardCharts>('/dashboard/charts'),
};

// Dashboard Preferences
export const dashboardPrefAPI = {
  widgets: () => request<{ id: string; label: string; category: string }[]>('/dashboard-pref/widgets'),
  get: () => request<{ widgets: string[] }>('/dashboard-pref/'),
  update: (widgets: string[]) => request<{ widgets: string[] }>('/dashboard-pref/', { method: 'PUT', body: JSON.stringify({ widgets }) }),
};

// Users
export const usersAPI = {
  list: () => request<User[]>('/users/'),
  create: (data: { username: string; email: string; full_name: string; password: string; role: string }) =>
    request<User>('/users/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: Partial<User & { password?: string }>) =>
    request<User>(`/users/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: number) => request(`/users/${id}`, { method: 'DELETE' }),
};

export interface BulkCommandResult {
  router_id: number;
  router_name: string;
  success: boolean;
  output: string;
  error?: string | null;
}

// RouterOS
export const routerosAPI = {
  testConnection: (data: { hostname: string; port: number; username: string; password: string; use_ssl: boolean }) =>
    request<{ success: boolean; identity?: string; version?: string; error?: string }>('/routeros/test-connection', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  command: (router_id: number, command: string) =>
    request<{ success: boolean; output: string; error?: string }>('/routeros/command', {
      method: 'POST',
      body: JSON.stringify({ router_id, command }),
    }),
  bulkCommand: (router_ids: number[], command: string) =>
    request<{ results: BulkCommandResult[] }>('/routeros/bulk-command', {
      method: 'POST',
      body: JSON.stringify({ router_ids, command }),
    }),
  ping: (router_id: number, target: string, count: number = 4) =>
    request<{ success: boolean; output: string; error?: string }>('/routeros/ping', {
      method: 'POST',
      body: JSON.stringify({ router_id, target, count }),
    }),
  configurePersistentLogging: (router_id: number) =>
    request<{ success: boolean; disk_created?: string[]; syslog_created?: string[]; configured?: string[]; error?: string }>('/routeros/logging/persistent', {
      method: 'POST',
      body: JSON.stringify({ router_id }),
    }),
  interfaces: (router_id: number) => request(`/routeros/interfaces/${router_id}`),
  resources: (router_id: number) => request(`/routeros/resources/${router_id}`),
  dhcp: (router_id: number) => request(`/routeros/dhcp/${router_id}`),
  arp: (router_id: number) => request(`/routeros/arp/${router_id}`),
  pppoe: (router_id: number) => request(`/routeros/pppoe/${router_id}`),
  firewall: (router_id: number) => request(`/routeros/firewall/${router_id}`),
  wireguard: (router_id: number) => request(`/routeros/wireguard/${router_id}`),
  configSection: (router_id: number, section: string) => request<any[]>(`/routeros/config/${router_id}/${section}`),
  wanConfig: (router_id: number) => request<{
    interfaces: { name: string; type: string; running: boolean }[];
    addresses: { interface: string; address: string; network: string }[];
    dhcp_clients: { interface: string; status: string; dhcp_server?: string; address?: string }[];
    pppoe_clients: { name: string; interface: string; status: string; user: string }[];
    dns_servers: string;
    gateway: string;
  }>(`/routeros/wan/${router_id}`),
  configureWan: (data: {
    router_id: number;
    wan_interface: string;
    wan_type: string;
    pppoe_user?: string;
    pppoe_password?: string;
    ip_address?: string;
    gateway?: string;
    dns_servers?: string;
  }) => request<{ success: boolean; message?: string; error?: string }>('/routeros/wan/configure', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
};

// Traffic (per-interface time-series)
export interface TrafficSample {
  timestamp: string;
  interface: string;
  rx_bps: number;
  tx_bps: number;
}

export const trafficAPI = {
  interfaces: (router_id: number) => request<string[]>(`/traffic/${router_id}/interfaces`),
  series: (router_id: number, params?: { interface?: string; hours?: number }) => {
    const query = new URLSearchParams();
    if (params?.interface) query.set('interface', params.interface);
    if (params?.hours) query.set('hours', String(params.hours));
    const qs = query.toString();
    return request<TrafficSample[]>(`/traffic/${router_id}${qs ? '?' + qs : ''}`);
  },
};

// Inventory
export const inventoryAPI = {
  list: (params?: { item_type?: string; search?: string }) => {
    const query = new URLSearchParams();
    if (params?.item_type) query.set('item_type', params.item_type);
    if (params?.search) query.set('search', params.search);
    const qs = query.toString();
    return request<InventoryItem[]>(`/inventory/${qs ? '?' + qs : ''}`);
  },
  create: (data: Partial<InventoryItem>) =>
    request<InventoryItem>('/inventory/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: Partial<InventoryItem>) =>
    request<InventoryItem>(`/inventory/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: number) => request(`/inventory/${id}`, { method: 'DELETE' }),
};

// Alerts
export const alertsAPI = {
  list: (params?: { is_resolved?: boolean; severity?: string; alert_type?: string; router_id?: number }) => {
    const query = new URLSearchParams();
    if (params?.is_resolved !== undefined) query.set('is_resolved', String(params.is_resolved));
    if (params?.severity) query.set('severity', params.severity);
    if (params?.alert_type) query.set('alert_type', params.alert_type);
    if (params?.router_id) query.set('router_id', String(params.router_id));
    const qs = query.toString();
    return request<Alert[]>(`/alerts/${qs ? '?' + qs : ''}`);
  },
  unresolvedCount: () => request<{ total: number; critical: number; warning: number; info: number }>('/alerts/unresolved-count'),
  resolve: (id: number, comment?: string) => request(`/alerts/${id}/resolve`, { method: 'PUT', body: JSON.stringify({ comment }) }),
  resolveAll: (comment?: string) => request('/alerts/resolve-all', { method: 'PUT', body: JSON.stringify({ comment }) }),
  listRules: () => request<AlertRule[]>('/alerts/rules/'),
  createRule: (data: Partial<AlertRule>) =>
    request<AlertRule>('/alerts/rules/', { method: 'POST', body: JSON.stringify(data) }),
  deleteRule: (id: number) => request(`/alerts/rules/${id}`, { method: 'DELETE' }),
};

// Templates
export const templatesAPI = {
  list: () => request<ConfigTemplate[]>('/templates/'),
  get: (id: number) => request<ConfigTemplate>(`/templates/${id}`),
  create: (data: Partial<ConfigTemplate>) =>
    request<ConfigTemplate>('/templates/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: Partial<ConfigTemplate>) =>
    request<ConfigTemplate>(`/templates/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: number) => request(`/templates/${id}`, { method: 'DELETE' }),
};

// Backups
export const backupsAPI = {
  list: (router_id?: number) => {
    const qs = router_id ? `?router_id=${router_id}` : '';
    return request<Backup[]>(`/backups/${qs}`);
  },
  create: (router_id: number, backup_type: string = 'binary') =>
    request(`/backups/backup/${router_id}`, {
      method: 'POST',
      body: JSON.stringify({ backup_type }),
    }),
  delete: (id: number) => request(`/backups/${id}`, { method: 'DELETE' }),
  download: (id: number, filename: string) => {
    const token = localStorage.getItem('mc_token');
    fetch(`/api/v1/backups/${id}/download`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => { if (!r.ok) throw new Error(`Error ${r.status}`); return r.blob(); })
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(err => console.error('Error descargando backup:', err));
  },
};

// Settings
export interface SystemSettings {
  smtp_host: string; smtp_port: string; smtp_user: string; smtp_password: string;
  smtp_from: string; smtp_tls: string;
  telegram_bot_token: string; telegram_chat_id: string;
  notify_router_offline: string; notify_router_online: string;
  notify_critical_alert: string; notify_warning_alert: string;
  notify_repeat_critical: string; notify_repeat_warning: string;
  notify_backup_complete: string; notify_high_cpu: string; notify_high_temp: string;
  notify_email_enabled: string; notify_telegram_enabled: string;
  health_check_interval: string; log_fetch_interval: string; history_fetch_interval: string;
  traffic_fetch_interval: string;
  health_alerts_enabled: string; log_alerts_enabled: string; history_alerts_enabled: string;
  event_retention_days: string; history_retention_days: string; traffic_retention_days: string;
  event_info_retention_days: string; unmatched_syslog_retention_days: string;
  backup_interval_hours: string;
  backup_schedule_days: string;
  backup_schedule_time: string;
  router_backup_interval_hours: string;
  router_backup_schedule_days: string;
  router_backup_schedule_time: string;
  router_backup_type: string;
  router_backup_retention_days: string;
  router_backup_retention_count: string;
  syslog_enabled: string;
  syslog_server_host: string;
  syslog_port: string;
  syslog_router_port: string;
  router_ntp_primary: string;
  router_ntp_secondary: string;
  router_time_zone: string;
  syslog_queue_max_size: string; syslog_worker_count: string;
  health_failures_to_offline: string; health_successes_to_online: string;
}

export interface OperatorUser {
  id: number; username: string; email: string; full_name: string;
  role: string; is_active: boolean; last_login: string | null;
}

export interface RoleItem {
  id: number;
  name: string;
  description: string;
  is_system: boolean;
  permissions: string[];
  event_categories: string[];
  router_scope: 'all' | 'selected';
  router_ids: number[];
  router_group_ids: number[];
  user_count: number;
}

export interface RoleOption {
  id: number;
  name: string;
  description: string;
}

export interface PermissionGroup {
  group: string;
  permissions: { key: string; label: string; description: string }[];
}

export const rolesAPI = {
  list: () => request<RoleItem[]>('/roles/'),
  options: () => request<RoleOption[]>('/roles/options'),
  get: (id: number) => request<RoleItem>(`/roles/${id}`),
  catalog: () => request<{ groups: PermissionGroup[]; all: string[] }>('/roles/permissions/catalog'),
  create: (data: { name: string; description?: string; permissions: string[]; event_categories?: string[]; router_scope?: 'all' | 'selected'; router_ids?: number[]; router_group_ids?: number[] }) =>
    request<RoleItem>('/roles/', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: { description?: string; permissions?: string[]; event_categories?: string[]; router_scope?: 'all' | 'selected'; router_ids?: number[]; router_group_ids?: number[] }) =>
    request<RoleItem>(`/roles/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (id: number) => request<{ detail: string }>(`/roles/${id}`, { method: 'DELETE' }),
};

export const settingsAPI = {
  get: () => request<SystemSettings>('/settings/'),
  update: (data: Partial<SystemSettings>) =>
    request<SystemSettings>('/settings/', { method: 'PUT', body: JSON.stringify(data) }),
  testEmail: () => request<{ success: boolean; message: string }>('/settings/test-email', { method: 'POST' }),
  testTelegram: () => request<{ success: boolean; message: string }>('/settings/test-telegram', { method: 'POST' }),
  backupDownload: () => {
    const token = localStorage.getItem('mc_token');
    fetch('/api/v1/settings/backup/download', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => { if (!r.ok) throw new Error(`Error ${r.status}`); return r.blob(); })
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `mikrocontrol_backup_${new Date().toISOString().slice(0, 10)}.db`;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(err => console.error('Error descargando backup de settings:', err));
  },
  eventFilters: () => request<{ filters: EventFilterRule[] }>('/settings/event-filters'),
  updateEventFilters: (filters: EventFilterRule[]) =>
    request<{ filters: EventFilterRule[] }>('/settings/event-filters', { method: 'PUT', body: JSON.stringify({ filters }) }),
  popupFilters: () => request<{ filters: EventFilterRule[] }>('/settings/popup-filters'),
  updatePopupFilters: (filters: EventFilterRule[]) =>
    request<{ filters: EventFilterRule[] }>('/settings/popup-filters', { method: 'PUT', body: JSON.stringify({ filters }) }),
  telegramFilters: () => request<{ filters: EventFilterRule[] }>('/settings/telegram-filters'),
  updateTelegramFilters: (filters: EventFilterRule[]) =>
    request<{ filters: EventFilterRule[] }>('/settings/telegram-filters', { method: 'PUT', body: JSON.stringify({ filters }) }),
  services: () => request<SystemServices>('/settings/services'),
  restartService: (name: string) => request<{ detail: string }>(`/settings/services/${name}/restart`, { method: 'POST' }),
  eventClassificationRules: () => request<{ rules: EventClassificationRule[] }>('/settings/event-classification-rules'),
  updateEventClassificationRules: (rules: EventClassificationRule[]) => request<{ rules: EventClassificationRule[] }>('/settings/event-classification-rules', { method: 'PUT', body: JSON.stringify({ rules }) }),
  filterGallery: () => request<{ filters: EventFilterRule[] }>('/settings/filter-gallery'),
  updateFilterGallery: (filters: EventFilterRule[]) => request<{ filters: EventFilterRule[] }>('/settings/filter-gallery', { method: 'PUT', body: JSON.stringify({ filters }) }),
  alertRecoveryRules: () => request<{ rules: AlertRecoveryRule[] }>('/settings/alert-recovery-rules'),
  updateAlertRecoveryRules: (rules: AlertRecoveryRule[]) => request<{ rules: AlertRecoveryRule[] }>('/settings/alert-recovery-rules', { method: 'PUT', body: JSON.stringify({ rules }) }),
  storageFilters: () => request<{ filters: EventFilterRule[] }>('/settings/storage-filters'),
  updateStorageFilters: (filters: EventFilterRule[]) => request<{ filters: EventFilterRule[] }>('/settings/storage-filters', { method: 'PUT', body: JSON.stringify({ filters }) }),
  storageUsage: () => request<StorageUsage>('/settings/storage-usage'),
  purgeStorage: () => request<{ deleted: Record<string, number> }>('/settings/storage-usage/purge', { method: 'POST' }),
};

export interface SystemServices { services: { name: string; label: string; status: string; canRestart: boolean }[]; resources: { load: number[]; cpuCount: number; memory: { total: number; available: number; used: number; percent: number }; disk: { total: number; used: number; free: number; percent: number }; database: { size: number; connections: number }; backupsSize: number; uptimeSeconds: number }; }
export interface StorageUsage { tables: { name: string; bytes: number; rows: number }[]; policies: { infoDays: number; eventDays: number; trafficDays: number; unmatchedDays: number }; }

export interface EventFilterRule {
  id: string;
  name: string;
  pattern: string;
  mode: 'contains' | 'wildcard' | 'regex';
  field: 'message' | 'topics' | 'any';
  enabled: boolean;
  roles?: string[];
}
export interface AlertRecoveryRule {
  id: string;
  name: string;
  enabled: boolean;
  opening: EventFilterRule;
  recovery: EventFilterRule;
  severity: 'warning' | 'critical';
  recovery_window_seconds: number;
  delay_notification: boolean;
  delay_seconds: number;
  force_recovery_report: boolean;
  resolution_comment: string;
}
export interface EventClassificationRule { id: string; name: string; pattern: string; field: 'message' | 'topics' | 'any'; mode: 'contains' | 'wildcard'; event_type: string; severity: 'critical' | 'warning' | 'info'; enabled: boolean; }

// Audit
export interface RouterHistoryEntry {
  id: number;
  router_id: number;
  router_name: string;
  ros_id: string;
  action: string;
  redo: string;
  undo: string | null;
  by_user: string;
  policy: string;
  ros_time: string;
  trace: string;
  undoable: string;
  first_seen: string | null;
}

export const auditAPI = {
  list: (params?: { page?: number; username?: string; action?: string; resource_type?: string; search?: string; date_from?: string; date_to?: string }) => {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.username) query.set('username', params.username);
    if (params?.action) query.set('action', params.action);
    if (params?.resource_type) query.set('resource_type', params.resource_type);
    if (params?.search) query.set('search', params.search);
    if (params?.date_from) query.set('date_from', params.date_from);
    if (params?.date_to) query.set('date_to', params.date_to);
    const qs = query.toString();
    return request<{ total: number; page: number; logs: AuditLogEntry[] }>(`/audit/${qs ? '?' + qs : ''}`);
  },
  filters: () => request<{ actions: string[]; resource_types: string[]; usernames: string[] }>('/audit/filters'),
  stats: () => request<{ total: number; by_action: { action: string; count: number }[]; by_resource: { resource_type: string; count: number }[]; by_user: { username: string; count: number }[] }>('/audit/stats'),
  routerHistory: (params?: { page?: number; router_id?: number; by_user?: string; search?: string; date_from?: string; date_to?: string }) => {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.router_id) query.set('router_id', String(params.router_id));
    if (params?.by_user) query.set('by_user', params.by_user);
    if (params?.search) query.set('search', params.search);
    if (params?.date_from) query.set('date_from', params.date_from);
    if (params?.date_to) query.set('date_to', params.date_to);
    const qs = query.toString();
    return request<{ total: number; page: number; entries: RouterHistoryEntry[] }>(`/audit/router-history${qs ? '?' + qs : ''}`);
  },
  routerHistoryFilters: () => request<{ routers: { id: number; name: string }[]; users: string[] }>('/audit/router-history/filters'),
  routerHistoryStats: () => request<{ total: number; by_router: { router_name: string; count: number }[]; by_user: { by_user: string; count: number }[] }>('/audit/router-history/stats'),
};

// Logo
export const logoAPI = {
  url: () => `${API_BASE}/logo/`,
  faviconUrl: () => `${API_BASE}/logo/favicon`,
  upload: async (file: File) => {
    const token = localStorage.getItem('mc_token');
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/logo/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Error' }));
      throw new Error(err.detail);
    }
    return res.json();
  },
  reset: () => request<{ detail: string }>('/logo/reset', { method: 'POST' }),
  faviconUpload: async (file: File) => {
    const token = localStorage.getItem('mc_token');
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/logo/favicon/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Error' }));
      throw new Error(err.detail);
    }
    return res.json();
  },
  faviconReset: () => request<{ detail: string }>('/logo/favicon/reset', { method: 'POST' }),
};

// Events (unified: router logs + health alerts)
export interface RouterEvent {
  id: string;
  router_id: number | null;
  router_name: string;
  time: string;
  topics: string;
  message: string;
  severity: string;
  created_at: string | null;
  source: 'router' | 'health';
  is_resolved?: boolean;
  resolved_at?: string | null;
  resolved_by?: string | null;
  resolution_comment?: string | null;
}

export const eventsAPI = {
  list: (params?: { severity?: string; topic?: string; router_id?: number; search?: string; source?: string; limit?: number; is_resolved?: boolean }) => {
    const query = new URLSearchParams();
    if (params?.severity) query.set('severity', params.severity);
    if (params?.topic) query.set('topic', params.topic);
    if (params?.router_id) query.set('router_id', String(params.router_id));
    if (params?.search) query.set('search', params.search);
    if (params?.source) query.set('source', params.source);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.is_resolved !== undefined) query.set('is_resolved', String(params.is_resolved));
    const qs = query.toString();
    return request<RouterEvent[]>(`/events/${qs ? '?' + qs : ''}`);
  },
  countsBySeverity: (params?: { source?: string; router_id?: number; search?: string; is_resolved?: boolean }) => {
    const query = new URLSearchParams();
    if (params?.source) query.set('source', params.source);
    if (params?.router_id) query.set('router_id', String(params.router_id));
    if (params?.search) query.set('search', params.search);
    if (params?.is_resolved !== undefined) query.set('is_resolved', String(params.is_resolved));
    const qs = query.toString();
    return request<{ critical: number; warning: number; info: number; unresolved: number }>(`/events/counts-by-severity${qs ? '?' + qs : ''}`);
  },
  refresh: () => request('/events/refresh', { method: 'POST' }),
  categories: () => request<{ key: string; label: string }[]>('/events/categories'),
  explorer: (params: { router_id?: number; severity?: string; event_type?: string; search?: string; date_from?: string; date_to?: string; page?: number; page_size?: number }) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== '') query.set(key, String(value)); });
    return request<EventExplorerResponse>(`/events/explorer?${query}`);
  },
  report: (router_id: number, date_from?: string, date_to?: string, event_type?: string) => {
    const query = new URLSearchParams({ router_id: String(router_id) });
    if (date_from) query.set('date_from', date_from);
    if (date_to) query.set('date_to', date_to);
    if (event_type) query.set('event_type', event_type);
    return request<EventReport>(`/events/report?${query}`);
  },
};

export interface EventExplorerItem { id: number; routerId: number; routerName: string; severity: string; eventType: string; topics: string; message: string; source: string; receivedAt: string; routerTime: string; }
export interface EventExplorerResponse { total: number; page: number; pageSize: number; items: EventExplorerItem[]; }
export interface EventReport { router: { id: number; name: string; clientName: string | null }; summary: { total: number; critical: number; warning: number; info: number }; series: { date: string; critical: number; warning: number; info: number }[]; from: string | null; to: string | null; periodDays: number; }

export interface SystemBackupItem {
  filename: string;
  size: number;
  created_at: string;
  created_at_display: string;
}

export const systemBackupAPI = {
  list: () => request<SystemBackupItem[]>('/system-backup/'),
  create: () => request<{ filename: string; size: number; message: string }>('/system-backup/create', { method: 'POST' }),
  download: (filename: string) => {
    const token = localStorage.getItem('mc_token');
    fetch(`/api/v1/system-backup/download/${filename}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => { if (!r.ok) throw new Error(`Error ${r.status}`); return r.blob(); })
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(err => console.error('Error descargando backup:', err));
  },
  restore: (filename: string) => request<{ message: string }>(`/system-backup/restore/${filename}`, { method: 'POST' }),
  deleteOne: (filename: string) => request<{ message: string }>(`/system-backup/${filename}`, { method: 'DELETE' }),
  deleteBulk: (filenames: string[]) => request<{ message: string; deleted: string[]; not_found: string[] }>('/system-backup/delete-bulk', { method: 'POST', body: JSON.stringify({ filenames }) }),
};

export const monitorAPI = {
  list: (since_event_log_id?: number) => {
    const query = since_event_log_id ? `?since_event_log_id=${since_event_log_id}` : '';
    return request<MonitorResponse>(`/monitor/${query}`);
  },
  notifications: (after_id: number, limit = 100) =>
    request<NotificationBatch>(`/monitor/notifications?after_id=${after_id}&limit=${limit}`),
  acknowledge: (id: number) => request<{ status: string }>(`/monitor/notifications/${id}/acknowledge`, { method: 'PUT' }),
};

export interface MonitorNotification {
  id: number; eventLogId: number | null; alertId: number | null; routerId: number | null;
  notificationType: string; severity: string; title: string; message: string;
  popupRequired: boolean; soundRequired: boolean; status: string; occurrenceCount: number; createdAt: string | null;
}
export interface NotificationBatch { items: MonitorNotification[]; nextCursor: number; hasMore: boolean; serverTimestamp: string; }

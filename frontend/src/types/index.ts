export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  permissions: string[];
  created_at: string | null;
  last_login: string | null;
}

export interface RouterDevice {
  id: number;
  name: string;
  hostname: string;
  ip_address: string;
  mac_address: string | null;
  model: string | null;
  serial_number: string | null;
  routeros_version: string | null;
  identity: string | null;
  access_method: string;
  access_port: number;
  use_ssl: boolean;
  api_username: string;
  group_id: number | null;
  tag_ids: number[];
  is_online: boolean;
  last_seen: string | null;
  cpu_usage: number | null;
  ram_usage: number | null;
  ram_total: number | null;
  temperature: number | null;
  voltage: number | null;
  uptime: string | null;
  hdd_free: number | null;
  hdd_total: number | null;
  latitude: number | null;
  longitude: number | null;
  address: string | null;
  city: string | null;
  client_name: string | null;
  client_phone: string | null;
  client_email: string | null;
  notes: string | null;
  wg_address: string | null;
  wg_endpoint: string | null;
  wg_public_key: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface RouterGroup {
  id: number;
  name: string;
  description: string | null;
  color: string;
  created_at: string | null;
}

export interface RouterTag {
  id: number;
  name: string;
  color: string;
}

export interface InventoryItem {
  id: number;
  item_type: string;
  name: string;
  brand: string | null;
  model: string | null;
  serial_number: string | null;
  mac_address: string | null;
  ip_address: string | null;
  location: string | null;
  client_name: string | null;
  status: string;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface Alert {
  id: number;
  router_id: number | null;
  alert_type: string;
  severity: string;
  title: string;
  message: string | null;
  is_resolved: boolean;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_comment: string | null;
  created_at: string | null;
}

export interface AlertRule {
  id: number;
  name: string;
  alert_type: string;
  threshold: number | null;
  severity: string;
  notify_telegram: boolean;
  notify_email: boolean;
  is_active: boolean;
  created_at: string | null;
}

export interface ConfigTemplate {
  id: number;
  name: string;
  description: string | null;
  category: string;
  template_content: string;
  variables: string | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface Backup {
  id: number;
  router_id: number;
  backup_type: string;
  filename: string;
  file_size: number | null;
  routeros_version: string | null;
  notes: string | null;
  is_restored: boolean;
  created_at: string | null;
}

export interface AuditLogEntry {
  id: number;
  user_id: number | null;
  username: string;
  action: string;
  resource_type: string;
  resource_id: number | null;
  resource_name: string | null;
  details: Record<string, unknown>;
  ip_address: string | null;
  timestamp: string | null;
}

export interface MonitorRouter {
  id: number;
  name: string;
  client_name: string | null;
  is_online: boolean;
  alert_count: number;
  critical_count: number;
  warning_count: number;
  max_critical_log_id: number;
  max_warning_log_id: number;
  last_seen: string | null;
  group_id: number | null;
  city: string | null;
}

export interface DashboardData {
  routers: { total: number; online: number; offline: number };
  metrics: { avg_cpu: number; avg_ram: number; avg_temp: number; avg_voltage: number; avg_hdd_free: number };
  alerts: { active: number; critical: number };
  inventory: { total: number };
  users: { total: number };
  today: { events: number; commands: number };
  wireguard: { tunnels: number };
  recent_activity: AuditLogEntry[];
}

export interface DashboardCharts {
  events_by_router: { router_name: string; count: number }[];
  top_topics: { topic: string; count: number }[];
  severity_by_hour: { hour: string; critical: number; warning: number; info: number }[];
  router_status: { online: number; offline: number };
  hardware_distribution: { model: string; count: number }[];
}

export const ROUTER_VIEW_PERMS = [
  'routers:view_interfaces', 'routers:view_traffic', 'routers:view_arp', 'routers:view_dhcp',
  'routers:view_pppoe', 'routers:view_firewall', 'routers:view_wireguard',
  'routers:view_addresses', 'routers:view_dns', 'routers:view_routes', 'routers:view_nat',
];

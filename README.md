# MikroControl

Sistema de gestión de routers MikroTik - Plataforma web completa.

## Requisitos

- Docker y Docker Compose
- 2GB RAM mínimo
- Puerto 80, 443, 5432 disponibles

## Instalación Rápida

```bash
# Clonar el repositorio
git clone <repo-url> MikroControl
cd MikroControl

# Copiar variables de entorno
cp .env.example .env

# Editar .env con tus datos (importante cambiar SECRET_KEY y DB_PASSWORD)
notepad .env

# Levantar todo
docker compose up -d

# Verificar
docker compose logs -f backend
```

## Acceso

- **URL:** http://localhost
- **Usuario:** admin
- **Contraseña:** se genera aleatoriamente en el primer inicio, salvo que se defina `MK_ADMIN_PASSWORD`.

Guardá la contraseña inicial y cambiala inmediatamente después del primer login.

## Arquitectura

```
MikroControl/
├── backend/          # FastAPI + Python
│   ├── app/
│   │   ├── api/v1/   # Endpoints REST
│   │   ├── core/     # Config, DB, Security
│   │   ├── models/   # SQLAlchemy models
│   │   ├── schemas/  # Pydantic schemas
│   │   └── services/ # RouterOS API, lógica
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/         # React + TypeScript + Tailwind
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── contexts/
│   │   ├── services/
│   │   └── types/
│   ├── Dockerfile
│   └── package.json
├── nginx/            # Reverse proxy
├── docker-compose.yml
└── .env.example
```

## Stack Tecnológico

| Componente | Tecnología |
|-----------|-----------|
| Backend | Python 3.12 + FastAPI |
| Base de datos | PostgreSQL 16 |
| Frontend | React 18 + TypeScript |
| CSS | Tailwind CSS |
| API MikroTik | RouterOS API (socket directo) |
| Tiempo real | WebSocket |
| Auth | JWT (Bearer token) |
| Despliegue | Docker Compose / systemd + Nginx |

## Roles de Usuario

| Rol | Permisos |
|-----|---------|
| Administrador | Todo: CRUD de todo, usuarios, eliminación |
| Supervisor | Gestión completa excepto eliminar usuarios |
| Técnico N2 | Editar routers, plantillas, backups |
| Técnico N1 | Verificar estado, ping, DHCP, backup |
| Auditor | Solo lectura |

## Módulos

### Dashboard NOC
- Routers online/offline
- CPU y RAM promedio
- Alertas activas
- Actividad reciente

### Gestión de Routers
- Alta, edición, eliminación
- Grupos y etiquetas
- Búsqueda rápida
- Filtros por grupo y estado

### RouterOS (conexión directa)
- Interfaces
- DHCP leases
- PPPoE activos
- Firewall rules
- WireGuard peers
- Terminal de comandos

### Plantillas
- Configuración RouterOS por categoría
- Variables personalizables
- Copiar al portapapeles

### Backups
- Binario y export
- Por router
- Versionado

### Alertas
- Reglas configurables
- Severidad: info, warning, critical
- Resolución de alertas

### Inventario
- Routers, switches, APs, cámaras, OLT, ONT, UPS, servidores
- Estados: activo, inactivo, mantenimiento

### Auditoría
- Registro completo de acciones
- Filtro por usuario
- Paginación

## API REST

Documentación Swagger disponible en: `http://localhost/api/docs`

### Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | /api/v1/auth/login | Login |
| GET | /api/v1/auth/me | Usuario actual |
| GET | /api/v1/dashboard/ | Datos dashboard |
| GET | /api/v1/routers/ | Listar routers |
| POST | /api/v1/routers/ | Crear router |
| POST | /api/v1/routers/{id}/check | Verificar estado |
| POST | /api/v1/routeros/command | Ejecutar comando |
| GET | /api/v1/routeros/interfaces/{id} | Interfaces |
| GET | /api/v1/routeros/dhcp/{id} | DHCP leases |
| GET | /api/v1/backups/ | Listar backups |
| POST | /api/v1/backups/backup/{id} | Crear backup |
| GET | /api/v1/audit/ | Logs de auditoría |

## Desarrollo Local (sin Docker)

### Backend
```bash
cd backend
pip install -r requirements.txt
# Necesitás PostgreSQL corriendo
export DATABASE_URL=postgresql://user:pass@localhost:5432/mikrocontrol
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Seguridad

- Cambiar SECRET_KEY y DB_PASSWORD en .env
- La configuración Docker incluida es para red interna y expone solamente Nginx en HTTP. Para publicar fuera de la LAN, terminá TLS en un proxy externo y restringí `CORS_ORIGINS` a los orígenes HTTPS autorizados.
- Crear usuarios con roles apropiados
- Revisar auditoría periódicamente
- Backups off-site recomendados

## Roadmap

- [x] Dashboard NOC
- [x] Gestión de routers
- [x] Roles y permisos
- [x] Conexión RouterOS API
- [x] Terminal integrada
- [x] Plantillas
- [x] Backups
- [x] Alertas
- [x] Inventario
- [x] Auditoría
- [ ] WebSocket monitoreo en tiempo real
- [ ] WireGuard Manager (full mesh)
- [ ] Alertas Telegram/Email
- [ ] Mapa interactivo
- [ ] WinBox launcher
- [ ] Comparador de configuraciones
- [ ] Hotspot manager
- [ ] PPPoE manager
- [ ] VLAN manager
- [ ] Scripts RouterOS
- [ ] Configuración masiva
- [ ] Multi-tenant

# Instalación de MikroControl v2 (PostgreSQL) en Ubuntu Server

> Versión 2.0: la base de datos es **PostgreSQL** (no SQLite). Esta guía asume un
> servidor Ubuntu 22.04+ limpio.

## Requisitos
- Ubuntu 22.04 o superior (recomendado 24.04 para Node 18+ nativo)
- Git
- Acceso a internet (para `apt`, `npm` y clonar el repo)

## Paso a paso

### 1. Dependencias del sistema
Incluye PostgreSQL, Nginx, Node (vía NodeSource para tener v18+) y
`libpq-dev`/`gcc` que necesita psycopg2.

> **Python:** el requirements.txt tiene versiones fijadas que NO tienen wheel
> para Python 3.14+. Por eso se instala **Python 3.12** vía el PPA deadsnakes
> (igual que el Dockerfile `python:3.12-slim`). No uses el `python3` del
> sistema si es 3.14.

```bash
sudo apt update
sudo apt install -y curl ca-certificates gnupg lsb-release software-properties-common

# Node.js 20 LTS (el de apt en 22.04 es muy viejo para Vite)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -

# Python 3.12 (necesario para las versiones fijadas de requirements.txt)
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev nginx nodejs git \
  postgresql postgresql-contrib libpq-dev gcc
```

### 2. Clonar el repositorio (v2)
```bash
sudo mkdir -p /opt/mikrocontrol
sudo git clone https://github.com/G057/MikroControlv2.git /opt/mikrocontrol
sudo chown -R $USER:$USER /opt/mikrocontrol
```

### 3. PostgreSQL - crear base y usuario
Generá una contraseña única. PostgreSQL queda accesible solamente desde el
servidor; no publiques el puerto 5432 en el firewall.

```bash
DB_PASSWORD=$(openssl rand -base64 32)
sudo -u postgres psql -v db_password="$DB_PASSWORD" -c "CREATE USER mikrocontrol WITH PASSWORD :'db_password';"
sudo -u postgres psql -c "CREATE DATABASE mikrocontrol OWNER mikrocontrol;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE mikrocontrol TO mikrocontrol;"
```

### 4. Backend - entorno virtual y dependencias
Usá **python3.12** (no el python3 del sistema si es 3.14).
```bash
cd /opt/mikrocontrol/backend
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

### 5. Variables de entorno
```bash
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
REDIS_PASSWORD=$(openssl rand -base64 32)
sudo install -o root -g www-data -m 640 /dev/null /opt/mikrocontrol/backend/.env
sudo tee /opt/mikrocontrol/backend/.env >/dev/null <<EOF
DATABASE_URL=postgresql://mikrocontrol:${DB_PASSWORD}@localhost:5432/mikrocontrol
SECRET_KEY=${SECRET_KEY}
CORS_ORIGINS=
REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6379/0
ROUTEROS_TLS_VERIFY=true
EOF
```
Para una instalación same-origin en la LAN, dejá `CORS_ORIGINS` vacío. Si un
frontend separado debe acceder a la API, agregá únicamente su origen HTTPS.

### 6. Migraciones de base de datos
En una instalación nueva, creá el esquema mediante Alembic antes de iniciar el
servicio:
```bash
cd /opt/mikrocontrol/backend
source venv/bin/activate
alembic upgrade head
deactivate
```
Para una base existente creada antes de Alembic: realizá y verificá un
`pg_dump`, detené el servicio, comprobá el esquema en una copia y recién
entonces ejecutá `alembic stamp 20260716_01`. No ejecutes `upgrade` sobre una
base existente sin el `stamp`, porque la revisión inicial crea las tablas.

### 7. Frontend - build de producción
```bash
cd /opt/mikrocontrol/frontend
npm ci
npm run build
```

### 8. Configurar nginx (puerto 8094)
```bash
sudo cp /opt/mikrocontrol/deploy/nginx-mikrocontrol.conf /etc/nginx/sites-available/mikrocontrol
sudo ln -s /etc/nginx/sites-available/mikrocontrol /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### 9. Configurar systemd (auto-inicio del backend en puerto 8001)
```bash
sudo cp /opt/mikrocontrol/deploy/mikrocontrol.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mikrocontrol
```

### 10. Corregir permisos (importante)
```bash
sudo chown -R www-data:www-data /opt/mikrocontrol/backend/backups /opt/mikrocontrol/backend/static/logo
sudo chown -R www-data:www-data /opt/mikrocontrol/frontend/dist
```

### 11. Iniciar el backend
```bash
sudo systemctl start mikrocontrol
sleep 5
sudo systemctl status mikrocontrol
```
Verificá que diga `active (running)`. Si falla, revisá logs:
```bash
sudo journalctl -u mikrocontrol -n 50 --no-pager
```

### 12. Abrir puerto en firewall
```bash
sudo ufw allow 8094/tcp
sudo ufw reload
```

### 13. Acceder
Abrí en el navegador: `http://IP_DEL_SERVIDOR:8094`

El primer inicio crea el usuario **admin** con contraseña aleatoria. Para verla:
```bash
sudo journalctl -u mikrocontrol | grep -i "contrase"
```

Si necesitás restablecerla, usá una contraseña aleatoria segura:
```bash
cd /opt/mikrocontrol/backend
source venv/bin/activate
python3 << 'EOF'
from app.core.security import get_password_hash
from app.core.database import SessionLocal
from app.models.user import User

db = SessionLocal()
admin = db.query(User).filter(User.username == "admin").first()
if admin:
    import secrets
    password = secrets.token_urlsafe(18)
    admin.hashed_password = get_password_hash(password)
else:
    import secrets
    password = secrets.token_urlsafe(18)
    admin = User(username="admin", email="admin@mikrocontrol.local",
                  full_name="Administrador",
                  hashed_password=get_password_hash(password),
                  role="admin", is_active=True)
    db.add(admin)
db.commit()
db.close()
print(f"Admin listo. Nueva contraseña: {password}")
EOF
deactivate
sudo systemctl restart mikrocontrol
```

## Actualizar desde GitHub
```bash
cd /opt/mikrocontrol
sudo git pull
cd /opt/mikrocontrol/frontend
npm ci
npm run build
sudo systemctl restart mikrocontrol
```

## Notas
- La base de datos es PostgreSQL: los backups se hacen con `pg_dump` y se
  restauran con `pg_restore` desde la sección "Backups" de la app. No existe
  ningún archivo `.db` que copiar.
- Si cambiás la password de PostgreSQL, actualizá `DATABASE_URL` en
  `deploy/mikrocontrol.service` y en `.env`, y recreá el servicio.

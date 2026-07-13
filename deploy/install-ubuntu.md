# Instalación de MikroControl v2 (PostgreSQL) en Ubuntu Server

> Versión 2.0: la base de datos es **PostgreSQL** (no SQLite). Esta guía asume un
> servidor Ubuntu 22.04+ limpio.

## Requisitos
- Ubuntu 22.04 o superior (recomendado 24.04 para Node 18+ nativo)
- Git
- Acceso a internet (para `apt`, `npm` y clonar el repo)

## Paso a paso

### 1. Dependencias del sistema
Incluye PostgreSQL, Nginx, Python, Node (vía NodeSource para tener v18+) y
`libpq-dev`/`gcc` que necesita psycopg2.

```bash
sudo apt update
sudo apt install -y curl ca-certificates gnupg lsb-release

# Node.js 20 LTS (el de apt en 22.04 es muy viejo para Vite)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -

sudo apt install -y python3 python3-venv python3-pip nginx nodejs npm git \
  postgresql postgresql-contrib libpq-dev gcc
```

### 2. Clonar el repositorio (v2)
```bash
sudo mkdir -p /opt/mikrocontrol
sudo git clone https://github.com/G057/MikroControlv2.git /opt/mikrocontrol
sudo chown -R $USER:$USER /opt/mikrocontrol
```

### 3. PostgreSQL - crear base y usuario
El `DATABASE_URL` por defecto usa usuario `mikrocontrol`, password
`mikrocontrol_secret_2026` y base `mikrocontrol`. Si querés otra password,
cambiala aquí y en `.env` + `deploy/mikrocontrol.service`.

```bash
sudo -u postgres psql -c "CREATE USER mikrocontrol WITH PASSWORD 'mikrocontrol_secret_2026';"
sudo -u postgres psql -c "CREATE DATABASE mikrocontrol OWNER mikrocontrol;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE mikrocontrol TO mikrocontrol;"
```

### 4. Backend - entorno virtual y dependencias
```bash
cd /opt/mikrocontrol/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

### 5. Variables de entorno
```bash
cd /opt/mikrocontrol
cp .env.example .env
# Permitir cualquier origen CORS (ajustá si querés restringir)
echo "CORS_ORIGINS=*" >> .env
```

### 6. Frontend - build de producción
```bash
cd /opt/mikrocontrol/frontend
npm install
npm run build
```

### 7. Configurar nginx (puerto 8094)
```bash
sudo cp /opt/mikrocontrol/deploy/nginx-mikrocontrol.conf /etc/nginx/sites-available/mikrocontrol
sudo ln -s /etc/nginx/sites-available/mikrocontrol /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### 8. Configurar systemd (auto-inicio del backend en puerto 8001)
El servicio ya define `DATABASE_URL` apuntando a PostgreSQL local.
```bash
sudo cp /opt/mikrocontrol/deploy/mikrocontrol.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mikrocontrol
```

### 9. Corregir permisos (importante)
```bash
sudo chown -R www-data:www-data /opt/mikrocontrol/backend
sudo chown -R www-data:www-data /opt/mikrocontrol/frontend/dist
sudo chmod -R 755 /opt/mikrocontrol/backend
```

### 10. Iniciar el backend
```bash
sudo systemctl start mikrocontrol
sleep 5
sudo systemctl status mikrocontrol
```
Verificá que diga `active (running)`. Si falla, revisá logs:
```bash
sudo journalctl -u mikrocontrol -n 50 --no-pager
```

### 11. Abrir puerto en firewall
```bash
sudo ufw allow 8094/tcp
sudo ufw reload
```

### 12. Acceder
Abrí en el navegador: `http://IP_DEL_SERVIDOR:8094`

El primer inicio crea el usuario **admin** con contraseña aleatoria. Para verla:
```bash
sudo journalctl -u mikrocontrol | grep -i "contrase"
```

Si no aparece o querés establecer una contraseña fija (`admin123`):
```bash
cd /opt/mikrocontrol/backend
source venv/bin/activate
python3 << 'EOF'
from app.core.database import Base, engine
from app.models import *
Base.metadata.create_all(bind=engine)

from app.core.security import get_password_hash
from app.core.database import SessionLocal
from app.models.user import User

db = SessionLocal()
admin = db.query(User).filter(User.username == "admin").first()
if admin:
    admin.hashed_password = get_password_hash("admin123")
else:
    admin = User(username="admin", email="admin@mikrocontrol.local",
                 full_name="Administrador",
                 hashed_password=get_password_hash("admin123"),
                 role="admin", is_active=True)
    db.add(admin)
db.commit()
db.close()
print("Admin listo (admin / admin123)")
EOF
deactivate
sudo systemctl restart mikrocontrol
```

## Actualizar desde GitHub
```bash
cd /opt/mikrocontrol
sudo git pull
cd /opt/mikrocontrol/frontend
npm install
npm run build
sudo systemctl restart mikrocontrol
```

## Notas
- La base de datos es PostgreSQL: los backups se hacen con `pg_dump` y se
  restauran con `pg_restore` desde la sección "Backups" de la app. No existe
  ningún archivo `.db` que copiar.
- Si cambiás la password de PostgreSQL, actualizá `DATABASE_URL` en
  `deploy/mikrocontrol.service` y en `.env`, y recreá el servicio.

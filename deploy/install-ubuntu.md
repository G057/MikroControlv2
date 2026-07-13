# Instalación de MikroControl en Ubuntu Server

## Requisitos
- Ubuntu 22.04 o superior
- Python 3.10+
- Node.js 18+
- Git

## Paso a paso

### 1. Dependencias del sistema
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx nodejs npm git
```

### 2. Clonar el repositorio
```bash
sudo mkdir -p /opt/mikrocontrol
sudo git clone https://github.com/TU_USUARIO/MikroControl.git /opt/mikrocontrol
sudo chown -R $USER:$USER /opt/mikrocontrol
```

### 3. Backend - entorno virtual y dependencias
```bash
cd /opt/mikrocontrol/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Variables de entorno
```bash
cd /opt/mikrocontrol
cp .env.example .env
# Opcional: permitir cualquier origen CORS
echo "CORS_ORIGINS=*" >> .env
```

### 5. Frontend - build producción
```bash
cd /opt/mikrocontrol/frontend
npm install
npm run build
```

### 6. Configurar nginx (puerto 8094)
```bash
sudo cp /opt/mikrocontrol/deploy/nginx-mikrocontrol.conf /etc/nginx/sites-available/mikrocontrol
sudo ln -s /etc/nginx/sites-available/mikrocontrol /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### 7. Configurar systemd (auto-inicio del backend)
```bash
sudo cp /opt/mikrocontrol/deploy/mikrocontrol.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mikrocontrol
```

### 8. Corregir permisos (importante)
```bash
sudo chown -R www-data:www-data /opt/mikrocontrol/backend
sudo chown -R www-data:www-data /opt/mikrocontrol/frontend/dist
sudo chmod -R 755 /opt/mikrocontrol/backend
```

### 9. Iniciar el backend
```bash
sudo systemctl start mikrocontrol
sleep 5
sudo systemctl status mikrocontrol
```

Verificar que esté `active (running)`.

### 10. Abrir puerto en firewall
```bash
sudo ufw allow 8094/tcp
sudo ufw reload
```

### 11. Acceder
Abrí en el navegador: `http://IP_DEL_SERVIDOR:8094`

El primer inicio crea el usuario **admin** con contraseña aleatoria. Para verla:
```bash
sudo journalctl -u mikrocontrol | grep "Contrase"
```

Si no aparece o querés establecer una contraseña fija:
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
print("Admin password: admin123")
EOF
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

## Migrar base de datos desde Windows

Copiar el archivo `backend/mikrocontrol.db` de Windows al servidor y luego:
```bash
sudo systemctl stop mikrocontrol
sudo cp /ruta/al/mikrocontrol.db /opt/mikrocontrol/backend/mikrocontrol.db
sudo chown www-data:www-data /opt/mikrocontrol/backend/mikrocontrol.db
sudo systemctl start mikrocontrol
```

# Rotación segura de SECRET_KEY

`SECRET_KEY` cifra las contraseñas API de routers y secretos de Telegram/SMTP.
No la reemplaces directamente: hacelo únicamente con este procedimiento.

## 1. Preparar

1. Confirmá que todos los routers estén online y que no haya errores
   `decrypt_secret` recientes.
2. Generá y verificá un backup PostgreSQL.
3. Detené el backend:

```bash
sudo systemctl stop mikrocontrol
```

## 2. Configurar ambas claves

Guardá una copia protegida del archivo de entorno y definí la nueva clave junto
con la anterior. No muestres los valores ni los pegues en tickets o chats.

```bash
OLD_SECRET=$(sudo sed -n 's/^SECRET_KEY=//p' /opt/mikrocontrol/backend/.env | head -n 1)
NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
sudo cp /opt/mikrocontrol/backend/.env /opt/mikrocontrol/backend/.env.before-secret-rotation
sudo chown root:www-data /opt/mikrocontrol/backend/.env.before-secret-rotation
sudo chmod 640 /opt/mikrocontrol/backend/.env.before-secret-rotation
sudo sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${NEW_SECRET}|" /opt/mikrocontrol/backend/.env
sudo sed -i '/^SECRET_KEY_PREVIOUS=/d' /opt/mikrocontrol/backend/.env
printf 'SECRET_KEY_PREVIOUS=%s\n' "$OLD_SECRET" | sudo tee -a /opt/mikrocontrol/backend/.env >/dev/null
```

## 3. Recifrar secretos

Iniciá el backend. Durante esta etapa puede leer secretos antiguos con
`SECRET_KEY_PREVIOUS`, pero los secretos guardados nuevos usan la nueva clave.

```bash
sudo systemctl start mikrocontrol
sudo -u www-data -H bash -c 'cd /opt/mikrocontrol/backend && /opt/mikrocontrol/backend/venv/bin/python -m scripts.rotate_secret_key'
```

El comando informa solamente cantidades, nunca valores secretos. Si falla, no
elimines `SECRET_KEY_PREVIOUS`; investigá el secreto inválido y reintentá.

## 4. Finalizar y validar

Eliminá el fallback, reiniciá y verificá que no existan errores de descifrado:

```bash
sudo sed -i '/^SECRET_KEY_PREVIOUS=/d' /opt/mikrocontrol/backend/.env
sudo systemctl restart mikrocontrol
sleep 75
sudo journalctl -u mikrocontrol --since "2 minutes ago" --no-pager | grep -Ei 'decrypt_secret|token inválido'
```

El último comando no debe devolver resultados. Los JWT previos quedan
invalidados por diseño: los usuarios deberán iniciar sesión nuevamente.

Conservá `.env.before-secret-rotation` hasta completar la validación y luego
eliminalo con un borrado controlado acorde a la política de la organización.

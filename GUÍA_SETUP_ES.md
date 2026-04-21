# Guía de instalación — Email Automation

---

## Índice

1. [¿Qué hace este programa?](#1-qué-hace-este-programa)
2. [Glosario](#2-glosario)
3. [Requisitos previos](#3-requisitos-previos)
4. [Paso 1: Instalar Python](#paso-1-instalar-python)
5. [Paso 2: Instalar uv](#paso-2-instalar-uv)
6. [Paso 3: Descargar el proyecto](#paso-3-descargar-el-proyecto)
7. [Paso 4: Instalar ngrok](#paso-4-instalar-ngrok)
8. [Paso 5: Colocar el archivo .env](#paso-5-colocar-el-archivo-env)
9. [Paso 6: Instalar las dependencias](#paso-6-instalar-las-dependencias)
10. [Paso 7: Autenticar con Outlook](#paso-7-autenticar-con-outlook)
11. [Paso 8: Iniciar ngrok](#paso-8-iniciar-ngrok)
12. [Paso 9: Actualizar BASE\_URL en .env](#paso-9-actualizar-base_url-en-env)
13. [Paso 10: Iniciar el programa](#paso-10-iniciar-el-programa)
14. [Paso 11: Verificar que todo funciona](#paso-11-verificar-que-todo-funciona)
15. [Cómo funciona Telegram](#cómo-funciona-telegram)
16. [Comandos útiles](#comandos-útiles)
17. [Solución de problemas](#solución-de-problemas)
18. [Preguntas frecuentes](#preguntas-frecuentes)

---

## 1. ¿Qué hace este programa?

El programa revisa tu correo de Outlook automáticamente y gestiona oportunidades de negocio.

**Lo que hace en orden:**

1. Cada 60 segundos revisa tu bandeja de entrada buscando correos no leídos de los últimos 7 días.
2. Guarda cada correo en una base de datos local.
3. Clasifica cada correo en una de tres categorías:
   - **Proveedor:** alguien que ofrece productos (ej: "Tengo 10 laptops HP disponibles").
   - **Cliente:** alguien que solicita una cotización (ej: "Necesito 5 laptops HP").
   - **Irrelevante:** correos que no tienen que ver con el negocio.
4. Busca coincidencias: si un cliente pidió algo que un proveedor ofrece, detecta la oportunidad.
5. Te avisa por Telegram con los datos del cliente, la oferta del proveedor y un borrador de respuesta listo para enviar.
6. Cuando presionas **Aprobar** en Telegram, el programa envía el correo al cliente desde tu cuenta de Outlook.
7. Marca el correo como leído en Outlook y en la base de datos para no procesarlo de nuevo.

---

## 2. Glosario

Estas son las palabras que aparecen a lo largo de la guía.

**Terminal** — Ventana de texto donde escribes comandos. En Windows se llama "Símbolo del sistema" o "PowerShell". En Mac se llama "Terminal". Se abre buscándola en el menú de inicio o con `Cmd + Espacio`.

**Python** — El lenguaje en que está escrito el programa. Necesitas instalarlo para que la computadora pueda ejecutarlo.

**uv** — Herramienta que instala automáticamente todo lo que el programa necesita para funcionar. Se instala una vez y luego se usa para arrancar el programa.

**Archivo .env** — Archivo de texto con las contraseñas y configuraciones del sistema (claves de Outlook, Telegram, inteligencia artificial, etc.). Lo entrega el administrador del proyecto. Contiene información sensible; no lo compartas ni lo subas a internet.

**Base de datos (SQLite)** — Archivo que guarda de forma organizada todos los correos, ofertas, solicitudes y coincidencias. Se llama `email_automation.db` y está en la carpeta `data/`.

**ngrok** — Programa que crea una dirección web temporal (URL) que apunta a tu computadora. Telegram la necesita para enviarte notificaciones. La URL cambia cada vez que reinicias ngrok.

**BASE\_URL** — La única variable del archivo `.env` que debes actualizar cada vez que ngrok reinicia. El programa la usa para todo lo relacionado con Telegram.

**Token** — Contraseña temporal que el programa usa para conectarse a tu cuenta de Outlook sin pedirte la clave cada vez. Se genera una vez y dura varios días o semanas.

---

## 3. Requisitos previos

- Computadora con Windows, Mac o Linux
- Conexión a internet
- Cuenta de Outlook (hotmail, outlook, live, o Microsoft 365 personal)
- Cuenta de Telegram con un bot configurado (el administrador ya lo hizo)
- El archivo `.env` con las credenciales (lo entrega el administrador)
- Permisos de administrador en la computadora para instalar programas

---

## Paso 1: Instalar Python

### En Windows

1. Abre tu navegador y ve a <https://www.python.org/downloads/>
2. Haz clic en el botón **Download Python**.
3. Abre el archivo descargado.
4. En la ventana de instalación, marca la casilla **"Add Python to PATH"** antes de continuar. Es importante hacerlo antes de presionar Install.
5. Presiona **Install Now** y espera a que termine.
6. Presiona **Close**.

Para verificar la instalación:

```
python --version
```

Debe aparecer algo como `Python 3.12.x`. Si aparece un error, reinicia la computadora e inténtalo de nuevo.

### En Mac

1. Ve a <https://www.python.org/downloads/>
2. Descarga e instala el archivo.
3. Para verificar:

```
python3 --version
```

Debe aparecer `Python 3.12.x`.

---

## Paso 2: Instalar uv

### En Windows

Abre **PowerShell** y ejecuta:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Cierra y vuelve a abrir PowerShell. Para verificar:

```
uv --version
```

### En Mac o Linux

Abre la Terminal y ejecuta:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Cierra y vuelve a abrir la Terminal. Para verificar:

```
uv --version
```

---

## Paso 3: Descargar el proyecto

### Si te dieron un archivo comprimido (ZIP)

1. Haz clic derecho sobre el archivo y selecciona **Extraer** o **Extract**.
2. Mueve la carpeta resultante (`email-automation`) a un lugar fácil de encontrar:
   - Windows: `C:\Users\TuNombre\Proyectos\email-automation`
   - Mac: `/Users/TuNombre/Proyectos/email-automation`

### Si te dieron acceso a GitHub

1. Ve al repositorio.
2. Haz clic en **Code → Download ZIP**.
3. Descomprime el archivo.

La carpeta del proyecto debe verse así:

```
email-automation/
├── data/
│   ├── attachments/
│   └── msal_token_cache.json
├── src/
│   └── email_automation/
├── tests/
├── .env.example
├── GUÍA_SETUP_ES.md
├── pyproject.toml
└── README.md
```

---

## Paso 4: Instalar ngrok

### En Windows

1. Ve a <https://ngrok.com/download> y descarga la versión para Windows.
2. Descomprime el archivo. Dentro hay un archivo llamado `ngrok.exe`.
3. Copia `ngrok.exe` dentro de la carpeta del proyecto (`email-automation/`).

### En Mac

1. Ve a <https://ngrok.com/download> y descarga la versión para Mac.
2. Descomprime y copia el archivo `ngrok` dentro de la carpeta del proyecto.

### Crear una cuenta y autenticar ngrok

1. Crea una cuenta gratuita en <https://dashboard.ngrok.com/signup>
2. Ve a <https://dashboard.ngrok.com/get-started/your-authtoken> y copia tu token.
3. Abre la terminal en la carpeta del proyecto y ejecuta:

   ```
   ./ngrok authtoken TU_TOKEN_AQUI
   ```

---

## Paso 5: Colocar el archivo .env

1. Recibe el archivo `.env` del administrador del proyecto.
2. Cópialo dentro de la carpeta `email-automation/`, al mismo nivel que `README.md` y `pyproject.toml`.

El archivo tiene esta estructura:

```env
MICROSOFT_AUTH_MODE=delegated
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxx
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
MICROSOFT_TENANT_ID=consumers
MICROSOFT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MICROSOFT_CLIENT_SECRET=
MICROSOFT_MAILBOX=
MICROSOFT_TOKEN_CACHE_PATH=data/msal_token_cache.json
TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ
TELEGRAM_CHAT_ID=123456789
TELEGRAM_WEBHOOK_SECRET=mi-clave-secreta-123
BASE_URL=https://xxxx-xx-xx-xx-xx.ngrok-free.app
DATABASE_URL=sqlite+aiosqlite:///./data/email_automation.db
ATTACHMENT_STORAGE_PATH=data/attachments
POLLING_INTERVAL_SECONDS=60
MATCH_THRESHOLD=65
SUPPLIER_OFFER_TTL_DAYS=30
COMPANY_NAME=Mantenimicros
SALES_SIGNATURE=Equipo Comercial
```

La única línea que tendrás que editar con frecuencia es `BASE_URL`, cada vez que ngrok reinicie. El resto no cambia.

---

## Paso 6: Instalar las dependencias

1. Abre la terminal.
2. Navega a la carpeta del proyecto:

   **Windows:**

   ```powershell
   cd C:\Users\TuNombre\Proyectos\email-automation
   ```

   **Mac:**

   ```bash
   cd /Users/TuNombre/Proyectos/email-automation
   ```

3. Ejecuta:

   ```bash
   uv sync
   ```

4. Espera a que termine. Verás varias líneas descargando paquetes. Al finalizar no debería haber errores.

---

## Paso 7: Autenticar con Outlook

Este paso se hace una sola vez. Genera el token que permite al programa leer tu correo.

1. En la terminal, dentro de la carpeta del proyecto, ejecuta:

   ```bash
   uv run email-automation-auth
   ```

2. Aparecerá un mensaje como este:

   ```
   To sign in, use a web browser to open the page https://microsoft.com/devicelogin
   and enter the code ABCD1234 to authenticate.
   ```

3. Copia el código (ej: `ABCD1234`).
4. Abre el navegador y ve a <https://microsoft.com/devicelogin>
5. Pega el código y presiona **Next**.
6. Inicia sesión con tu cuenta de Outlook y acepta los permisos solicitados.
7. Vuelve a la terminal. Debe aparecer:

   ```
   Microsoft Graph authentication succeeded and the token cache was updated at data/msal_token_cache.json
   ```

**Configuración requerida en el .env para cuentas personales** (@outlook.com, @hotmail.com, @live.com):

```
MICROSOFT_AUTH_MODE=delegated
MICROSOFT_TENANT_ID=consumers
MICROSOFT_CLIENT_SECRET=   ← debe estar vacío
```

---

## Paso 8: Iniciar ngrok

1. Abre una terminal nueva (mantén la anterior abierta).
2. Navega a la carpeta del proyecto.
3. Ejecuta:

   ```bash
   ./ngrok http 8000
   ```

4. Verás una pantalla como esta:

   ```
   Session Status    online
   Forwarding        https://abcd-123-456-789-012.ngrok-free.app -> http://localhost:8000
   ```

5. Copia la URL que empieza con `https://` (en el ejemplo: `https://abcd-123-456-789-012.ngrok-free.app`).
6. Deja esta terminal abierta. Si la cierras, ngrok se detiene y Telegram deja de funcionar.

---

## Paso 9: Actualizar BASE\_URL en .env

1. Abre el archivo `.env` con cualquier editor de texto.
2. Busca la línea:

   ```
   BASE_URL=https://xxxx-xx-xx-xx-xx.ngrok-free.app
   ```

3. Reemplaza la URL por la que copiaste de ngrok:

   ```
   BASE_URL=https://abcd-123-456-789-012.ngrok-free.app
   ```

4. Guarda el archivo (`Ctrl + S` en Windows, `Cmd + S` en Mac).

Esta es la única URL que necesitas actualizar. El programa la usa también para conectarse con Telegram.

---

## Paso 10: Iniciar el programa

1. Abre una terminal nueva (sin cerrar las anteriores).
2. Navega a la carpeta del proyecto.
3. Ejecuta:

   ```bash
   uv run email-automation
   ```

4. Cuando veas esto, el programa está funcionando:

   ```
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

5. Deja esta terminal abierta.

En este punto tienes dos terminales activas:

- Terminal 1: ngrok
- Terminal 2: el programa

---

## Paso 11: Verificar que todo funciona

### 11.1 Verificar el servidor

Abre el navegador y ve a:

```
http://localhost:8000/health
```

Debe aparecer:

```json
{"status":"ok"}
```

### 11.2 Verificar Telegram

1. Abre Telegram y busca el bot configurado.
2. Envía `/start`.
3. Si el bot responde, la conexión está funcionando.

### 11.3 Procesar correos manualmente

El programa revisa el correo cada 60 segundos. Para forzar una revisión inmediata:

```bash
curl -X POST http://localhost:8000/internal/process-inbox
```

En Windows con PowerShell:

```powershell
Invoke-WebRequest -Uri http://localhost:8000/internal/process-inbox -Method POST
```

La respuesta indica cuántos correos procesó:

```json
{"processed":2,"skipped":0}
```

### 11.4 Revisar la base de datos (opcional)

Puedes inspeccionar la base de datos con [DB Browser for SQLite](https://sqlitebrowser.org/):

1. Instala y abre el programa.
2. Abre el archivo `data/email_automation.db`.
3. En la pestaña **Browse Data** puedes ver las tablas:
   - `email_messages`: correos procesados
   - `supplier_offers`: ofertas de proveedores
   - `client_requests`: solicitudes de clientes
   - `match_candidates`: coincidencias encontradas

---

## Cómo funciona Telegram

Cuando el programa detecta una coincidencia, te envía un mensaje como este:

```
Nueva coincidencia #15
Cliente: Juan Pérez <juan@empresa.com>
Solicitud: Necesito 5 laptops HP 840 G8
Oferta: HP 840 G8 i5 16GB 256GB — 520 USD
Score: 87.5

Asunto sugerido: Propuesta de equipos HP 840 G8

Estimado Juan,

Tenemos disponibles las laptops HP 840 G8 que solicitaste...
```

Con tres botones:

- **Aprobar** — envía el correo al cliente
- **Rechazar** — descarta la propuesta
- **Pedir ajuste** — solicita cambios al borrador

### Pedir ajuste

Cuando presionas "Pedir ajuste", el bot espera que escribas:

```
/revise 15 Agregar descuento del 10% por compra de 5 unidades
```

El programa reescribe el borrador con tus instrucciones y lo envía de nuevo.

---

## Comandos útiles

| Comando | Para qué sirve | Cuándo usarlo |
|---|---|---|
| `uv sync` | Instala las dependencias | Primera vez, o si el proyecto se actualiza |
| `uv run email-automation-auth` | Conecta con Outlook | Una vez al inicio; repetir si caduca la sesión |
| `uv run email-automation` | Inicia el programa | Cada vez que quieras que empiece a procesar correos |
| `uv run email-automation-reset-db` | Borra toda la base de datos | Solo para pruebas; no tiene vuelta atrás |
| `curl -X POST http://localhost:8000/internal/process-inbox` | Fuerza revisión inmediata del correo | Cuando no quieres esperar los 60 segundos |
| `./ngrok http 8000` | Inicia el túnel para Telegram | Cada vez que inicias el programa |

---

## Solución de problemas

### "No cached Microsoft Graph user token is available"

El programa perdió la conexión con Outlook. Ejecuta `uv run email-automation-auth` y completa el inicio de sesión de nuevo.

### "Unable to acquire Microsoft Graph token"

El programa no puede conectarse a Outlook. Verifica:

1. Que el archivo `.env` esté en la carpeta raíz del proyecto.
2. Que las credenciales de Microsoft sean correctas.
3. Tu conexión a internet.

### "TELEGRAM_BOT_TOKEN is required for Telegram actions"

Falta la clave de Telegram en el `.env`. Solicita el archivo actualizado al administrador.

### Telegram no envía mensajes

1. Verifica que ngrok esté corriendo.
2. Verifica que `BASE_URL` en `.env` tenga la URL actual de ngrok.
3. Reinicia el programa.

### El programa no procesa correos antiguos

El programa solo procesa correos no leídos de los últimos 7 días. Esto es el comportamiento esperado.

### La URL de ngrok cambió y Telegram dejó de funcionar

1. Detén ngrok con `Ctrl + C`.
2. Vuelve a ejecutar `./ngrok http 8000`.
3. Copia la nueva URL.
4. Actualiza `BASE_URL` en `.env`.
5. Reinicia el programa.

### Quiero detener todo

1. En la terminal del programa, presiona `Ctrl + C`.
2. En la terminal de ngrok, presiona `Ctrl + C`.

---

## Preguntas frecuentes

**¿Puedo apagar la computadora?**
Sí, pero el programa se detiene. Al encenderla de nuevo, tendrás que iniciar ngrok y el programa otra vez.

**¿Cuántas veces tengo que autenticar con Outlook?**
Una vez. El token dura varios días o semanas. Solo necesitas repetirlo si aparece un error de autenticación.

**¿Puedo usar la computadora mientras el programa corre?**
Sí. El programa trabaja en segundo plano y no interfiere con otras aplicaciones.

**¿Qué pasa si borro la base de datos?**
Perderás todo el historial de correos procesados y el programa empezará desde cero.

**¿Por qué solo revisa correos de los últimos 7 días?**
Para evitar procesar correos viejos que ya no son relevantes.

**¿El programa lee correos que ya marqué como leídos?**
No. Solo procesa correos marcados como no leídos en Outlook.

**¿Puede manejar múltiples proveedores y clientes al mismo tiempo?**
Sí.

**¿Qué pasa si un cliente pide algo y no hay proveedor que coincida?**
El programa envía una alerta a Telegram indicando que no hay stock disponible para esa solicitud.

**¿El programa envía correos por su cuenta?**
No. Solo envía correos cuando tú presionas "Aprobar" en Telegram.

---

## Flujo completo

```
┌──────────────────────────────────────────────────────────────┐
│                      TU COMPUTADORA                          │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │   Outlook   │───▶│  Programa   │───▶│  Base de datos  │  │
│  └─────────────┘    └──────┬──────┘    └─────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│                     ┌─────────────┐                          │
│                     │    ngrok    │                          │
│                     └──────┬──────┘                          │
└────────────────────────────┼─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                         INTERNET                             │
│                                                              │
│    ┌──────────────┐                 ┌──────────────┐         │
│    │ Telegram Bot │◀───────────────▶│  Tu celular  │         │
│    └──────────────┘                 └──────────────┘         │
└──────────────────────────────────────────────────────────────┘
```

1. Llega un correo a Outlook.
2. El programa lo detecta en la siguiente revisión (cada 60 segundos).
3. Lo guarda en la base de datos y lo clasifica.
4. Si hay una coincidencia cliente–proveedor, envía una notificación a Telegram.
5. Recibes el mensaje con el borrador de respuesta.
6. Presionas Aprobar, Rechazar o Pedir ajuste.
7. Si apruebas, el programa envía el correo al cliente desde Outlook.
8. El correo se marca como leído en Outlook y en la base de datos.

---

Para soporte, contacta al administrador del proyecto.

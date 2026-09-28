# SGR - Sistema de Gestión y Rendición

SGR es un sistema de gestión municipal desarrollado sobre Django para la administración de delegaciones territoriales, compromisos de la agenda colectiva, métricas operativas y rendición de cuentas de funcionarios.

---

## Arquitectura del Sistema

El sistema se compone de cuatro módulos principales respaldados por un modelo relacional de 9 entidades (compatible con MySQL y SQLite):

- **`cuentas`**: Autenticación, gestión de sesiones basada en roles, perfiles de funcionarios (`StaffProfile`) y escritorio principal.
- **`organizacion`**: Delegaciones territoriales (`Delegation`), catálogo global de cargos (`Position`) y administración del ciclo de vida de delegaciones.
- **`agenda`**: Compromisos de la agenda colectiva (`Commitment`) y registro cronológico inmutable de eventos (`CommitmentEvent`).
- **`indicadores`**: Periodos de evaluación (`Period`), catálogo de métricas (`MetricItem`) y metas individuales por funcionario (`StaffTarget`).

---

## Requisitos

- Python 3.12+
- MySQL 8.x / MariaDB (o SQLite para pruebas locales livianas)
- Compilador C/C++ o paquetes binarios (wheels) para `mysqlclient`

---

## Guía de Instalación y Puesta en Marcha

### 1. Clonar el repositorio

```bash
git clone https://github.com/Jano03op/Proyecto-Integrado.git
cd Proyecto-Integrado
```

### 2. Crear y activar el entorno virtual

```bash
python -m venv venv

# En Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# En Linux / macOS:
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

El sistema utiliza variables de entorno para mantener la seguridad y el aislamiento entre entornos. Puedes guiarte con el archivo `.env.example`.

#### Opción A: Desarrollo local con MySQL (ej. WampServer en puerto 3306)

En PowerShell:

```powershell
$env:SECRET_KEY="tu-clave-secreta-local"
$env:DEBUG="True"
$env:ALLOWED_HOSTS="localhost,127.0.0.1"
$env:DB_BACKEND="mysql"
$env:DB_NAME="sgr_db"
$env:DB_USER="root"
$env:DB_PASSWORD=""
$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
```

#### Opción B: Desarrollo local con SQLite

En PowerShell:

```powershell
$env:SECRET_KEY="tu-clave-secreta-local"
$env:DEBUG="True"
$env:ALLOWED_HOSTS="localhost,127.0.0.1"
$env:DB_BACKEND="sqlite"
```

### 5. Aplicar migraciones a la base de datos

```bash
python manage.py migrate
```

### 6. Cargar datos iniciales (Opcional)

Si dispones del archivo fuente `datosarray.json`, puedes utilizar el comando de importación y conciliación:

```bash
# Simulación sin escritura (dry-run):
python manage.py import_sgr_data --dry-run

# Importación definitiva:
python manage.py import_sgr_data
```

Para crear un usuario administrador manualmente:

```bash
python manage.py createsuperuser
```

### 7. Iniciar el servidor de desarrollo

```bash
python manage.py runserver 127.0.0.1:8000
```

Acceso en el navegador:
- **Portal de inicio**: `http://127.0.0.1:8000/`
- **Inicio de sesión**: `http://127.0.0.1:8000/cuentas/login/`
- **Panel de administración Django**: `http://127.0.0.1:8000/admin/`

---

## Ejecución de Pruebas Automatizadas

Para validar la integridad de todos los módulos y reglas de negocio:

```bash
python manage.py test organizacion cuentas indicadores agenda
```

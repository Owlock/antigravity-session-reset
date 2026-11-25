# antigravity-session-reset

[English](README.md) · [Guía manual de SQLite](docs/sqlite-manual.md) · [Caso de Windows anonimizado](docs/case-study.es.md)

Guía y herramienta local para cambiar de cuenta cuando Antigravity recuerda el correo anterior, repite el inicio de sesión o muestra Free después de elegir una cuenta con Pro. Comprueba primero en Google qué correo tiene la suscripción.

Un usuario de Windows confirmó que pudo iniciar sesión desde cero y conservar chats, artefactos, extensiones y ajustes. El script se probó además con datos ficticios en Windows. Falta comprobar la ejecución completa en equipos macOS y Linux.

## Qué cambia

| Destino | Operación |
|---|---|
| Base principal `User/globalStorage/state.vscdb` | Elimina únicamente las filas aprobadas que existan. Conserva las demás, incluidas `google.antigravity` y `antigravityUnifiedStateSync.trajectorySummaries`. |
| Ambas aplicaciones | Selecciona `antigravityUnifiedStateSync.oauthToken`, `antigravityUnifiedStateSync.userStatus` y `antigravityUnifiedStateSync.modelCredits`. En versiones anteriores puede existir `jetskiStateSync.agentManagerInitState`; se elimina solo si está presente. |
| Solo Antigravity | Selecciona también `antigravityAuthStatus`, `antigravityAnalytics.clearcutBuffer`, `antigravityAnalytics.lastUploadTime`, `antigravityOnboarding` y `antigravityUnifiedStateSync.onboarding`. Incluyen datos de actividad y bienvenida. |
| Datos web | Respalda y retira `Cache`, `Code Cache`, `Network`, `Session Storage` y `Local Storage`, directamente dentro de cada carpeta de datos. Pueden guardar preferencias de la interfaz web. |
| Credenciales | Selecciona la credencial genérica exacta `gemini:antigravity` en Windows y el archivo `~/.gemini/jetski-standalone-oauth-token` si existe. En macOS/Linux el usuario selecciona la entrada antigua del llavero. |
| Navegador interno | Solo con `--include-browser-profile` se respalda y retira `~/.gemini/antigravity-browser-profile/`, con sus preferencias y cookies. |
| Datos personales | Conserva `extensions/`, `brain/`, `conversations/`, atajos, ajustes, bases de proyectos y respaldos anteriores. Si aparece `~/.gemini/antigravity-acp/`, pide revisarla manualmente. |

El símbolo `~` representa tu carpeta personal, también en Windows. Haz la limpieza antes de entrar con tu cuenta nueva: los datos de sesión pertenecen al perfil local de la aplicación.

## Procedimiento completamente manual

1. **Cierra los programas.** Guarda tu trabajo y sal de las dos variantes de Antigravity, de `agy` y del navegador interno. En Windows pulsa **Ctrl+Mayús+Esc** y busca **Detalles**. En macOS pulsa **Comando+Espacio**, escribe **Monitor de Actividad** y pulsa Intro. En Linux busca **Monitor del sistema** en tus aplicaciones, o escribe `ps -A -o comm=` en Terminal. Busca Antigravity, `agy` y su `language_server`, el proceso auxiliar. Si ves uno que podría ser de otro editor, identifica a quién pertenece antes de cerrarlo.
2. **Localiza las carpetas.** En Windows pulsa **Windows+E**, luego **Alt+D**, escribe `%APPDATA%` y pulsa Intro. Repite con `%LOCALAPPDATA%`. En macOS abre Finder y selecciona **Ir → Ir a la carpeta** para revisar `~/Library/Application Support` y `~/Library/Caches`. En Linux pulsa **Ctrl+L** en el gestor de archivos y prueba `~/.config` y `~/.cache`, o tus carpetas `XDG_CONFIG_HOME` y `XDG_CACHE_HOME` si las personalizaste. Dentro busca `Antigravity` y `Antigravity IDE`. Salta las ausentes. Las instalaciones portátiles o aisladas pueden usar otra ubicación.
3. **Respalda antes de cambiar.** En una ubicación privada, fuera de los datos de la app, del repositorio y de la nube, crea una carpeta con fecha y hora. Conserva las rutas relativas. Dentro de cada aplicación, revisa solo `User/settings.json`, `User/globalStorage/state.vscdb` y `User/workspaceStorage/*/state.vscdb`. El asterisco representa una carpeta de proyecto de primer nivel. Copia esos archivos y cada destino que pienses retirar. Las bases y los ajustes deben pesar más de cero bytes. Para comparar una copia usa SHA-256, una huella del contenido: en PowerShell ejecuta `Get-FileHash -LiteralPath 'ARCHIVO'`; en Terminal de macOS, `shasum -a 256 "ARCHIVO"`; en Terminal de Linux, `sha256sum "ARCHIVO"`. Sustituye `ARCHIVO` primero por la ruta del original y luego por la copia. Las dos huellas deben coincidir. Si ves `-wal`, `-shm` o `-journal` junto a una base, conserva esos archivos: pueden contener cambios pendientes. Comprueba el cierre limpio antes de seguir.
4. **Edita solo las bases principales.** Para cada `User/globalStorage/state.vscdb` existente sigue la [guía manual de SQLite](docs/sqlite-manual.md). Incluye las claves, la comprobación del historial y cómo recuperar filas. En Antigravity IDE salta el bloque exclusivo de Antigravity.
5. **Retira los datos seleccionados.** Dentro de cada carpeta de datos confirmada, envía a la Papelera las cinco carpetas web de la tabla. Conserva `User/`. En `~/.gemini` retira el archivo independiente de token si existe. Retira el perfil del navegador interno solo si quieres borrar también sus preferencias y verificaste su copia. Si dudas del contenido de `antigravity-acp/`, consérvala.
6. **Retira la credencial antigua.** Utiliza tu cuenta habitual del sistema:
   - **Windows:** pulsa **Windows+R**, escribe `cmd` y pulsa Intro. Ejecuta `cmdkey /list:gemini:antigravity`. Si identificas la entrada correcta, ejecuta `cmdkey /delete:gemini:antigravity`. Repite el primer comando para comprobar que desapareció. No necesitas elevar permisos.
   - **macOS:** pulsa **Comando+Espacio** y busca **Acceso a Llaveros**. Allí busca `Antigravity`, comprueba el servicio, la cuenta y el llavero, y elimina la entrada antigua. En Terminal, tras definir las tres variables con esos datos comprobados, el equivalente es `security delete-generic-password -s "${AG_SERVICE:?}" -a "${AG_ACCOUNT:?}" "${AG_KEYCHAIN:?}"`. Para empezar es más sencillo seleccionar el elemento en la ventana.
   - **Linux:** busca **Contraseñas y claves**. Si tienes Seahorse, escribir `seahorse` en Terminal abre la ventana. Revisa los campos identificativos de la entrada y elimina solo la antigua. En un llavero compatible, el equivalente es `secret-tool clear "${AG_KEY1:?}" "${AG_VALUE1:?}" "${AG_KEY2:?}" "${AG_VALUE2:?}"` después de definir dos pares de campos y valores que identifiquen un único elemento. Este comando puede eliminar todas las coincidencias desbloqueadas. Otros escritorios tienen gestores distintos. Si pide desbloqueo, hazlo en su ventana habitual.
7. **Termina en el navegador externo.** Pulsa la foto de la cuenta antigua y verifica el correo. Entra en [Conexiones de Google](https://myaccount.google.com/connections). Si aparece Antigravity, entra en sus detalles y retira el acceso. En Chrome pulsa **⋮ → Configuración → Privacidad y seguridad → Cookies de terceros → Ver todos los datos y permisos de sitios**. Busca `antigravity.google` y borra únicamente sus datos. Abre una ventana de incógnito o un perfil separado. Inicia Antigravity y elige iniciar sesión. Si abre una pestaña normal, copia esa dirección a la ventana aislada. Comprueba el correo nuevo antes de aceptar y mantén privada la dirección de acceso.
8. **Prueba el resultado.** Comprueba el correo y el plan que muestra la aplicación. Abre una conversación anterior y un artefacto y revisa las extensiones y preferencias. Si el plan también es incorrecto en Google para ese mismo correo, revisa allí la suscripción antes de repetir el procedimiento.

## Usar el script

Necesitas Python 3.10 o posterior con SQLite. Solo usa la biblioteca estándar. No requiere red ni permisos elevados. Abre una terminal en la carpeta del repositorio. En Windows puedes escribir `cmd` en la barra de dirección de esa carpeta y pulsar Intro. Si tu equipo reconoce `python` o `py -3`, utiliza ese nombre en lugar de `python3`. Añadir `--version` muestra la versión instalada.

```sh
python3 -B ag_session_reset.py
python3 -B ag_session_reset.py --dry-run --include-browser-profile
python3 -B ag_session_reset.py --apply --include-browser-profile
```

Los dos primeros comandos muestran una vista previa de solo lectura. Solo `--apply` autoriza cambios. Omite `--include-browser-profile` si quieres conservar el navegador interno. `--backup-dir "RUTA"` permite elegir una carpeta local privada para los respaldos. Por defecto se guardan en `~/.ag-session-backups/`. Dentro de cada copia fechada, `roaming/`, `support/`, `config/`, `cache/` o `gemini/` indican el origen.

El script comprueba los procesos y muestra solo el nombre del ejecutable que impide seguir. Valida las rutas normalizadas antes de editar SQLite. Dentro de `User/` revisa únicamente los archivos indicados en el paso 3 y omite los proyectos que sean enlaces. Se detiene ante un destino enlazado, una base con cambios pendientes o un tipo de archivo inesperado. También se detiene si el sistema carece de una herramienta para consultar los procesos.

En bases, ajustes y token se compara tamaño y SHA-256 al copiar y se vuelven a verificar original y respaldo antes de editar. En las carpetas web y el perfil del navegador se lee cada archivo de origen una vez y la copia una vez; los controles posteriores revisan nombres, tipos y metadatos. Mantén la aplicación cerrada. En Windows el script puede reintentar la eliminación de una caché de solo lectura. Cada base se confirma por separado después de comparar las filas conservadas y ejecutar `PRAGMA integrity_check;`. El llavero se trata al final.

## Recuperación y privacidad

Si algo falla, conserva el **primer respaldo verificado** y mantén la aplicación cerrada. Puede haber pasos ya completados. Recupera la carpeta web que necesites desde su ubicación correspondiente en el respaldo. Para recuperar filas usa la [guía de recuperación selectiva](docs/sqlite-manual.md). La credencial del llavero se vuelve a crear al iniciar sesión. Si una interrupción deja `~/.ag-session-reset.lock/`, comprueba en el gestor de procesos que no haya otro Python ejecutando `ag_session_reset.py`. Retira únicamente esa carpeta vacía después de verificarlo.

Los respaldos pueden contener datos de acceso reutilizables. Tras verificar la cuenta nueva y los datos personales, elimina la copia que ya no necesites y vacía la Papelera si corresponde. Evita compartir bases, listados del llavero, correos y direcciones de acceso en informes públicos.

## Pruebas

En la carpeta del repositorio, `python3 -B -m unittest discover -s tests -v` ejecuta las pruebas. Crean perfiles temporales, sustituyen el llavero por una simulación en memoria, bloquean el acceso nativo a credenciales y eliminan las carpetas de prueba. En Windows se probaron las dos variantes de borrado con Python 3.10 y 3.12. La validación en macOS y Linux sigue pendiente.

Proyecto comunitario independiente de Google. [Licencia MIT](LICENSE).

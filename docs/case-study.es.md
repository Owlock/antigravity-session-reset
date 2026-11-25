# Auditoría anonimizada del cambio de cuenta en Windows

El usuario confirmó que, después de limpiar los datos locales de la cuenta anterior, pudo entrar en Antigravity con su cuenta Pro y seguir usando sus conversaciones, artefactos, extensiones y ajustes.

## Operaciones observadas

- Se retiró del llavero de Windows la entrada exacta `gemini:antigravity`. Se comprobó que los demás destinos seguían presentes.
- En las dos bases principales se retiraron `antigravityUnifiedStateSync.oauthToken`, `antigravityUnifiedStateSync.userStatus` y `antigravityUnifiedStateSync.modelCredits`.
- Solo en Antigravity se retiraron además `antigravityAuthStatus`, `antigravityAnalytics.clearcutBuffer`, `antigravityAnalytics.lastUploadTime`, `antigravityOnboarding` y `antigravityUnifiedStateSync.onboarding`. El caso no permite saber cuáles eran imprescindibles.
- Se respaldaron y retiraron `Cache`, `Code Cache`, `Network`, `Session Storage` y `Local Storage` en cada aplicación. Se respaldó y retiró `~/.gemini/antigravity-browser-profile/` por decisión expresa del usuario.
- `~/.gemini/jetski-standalone-oauth-token` y `~/.gemini/antigravity-acp/` estaban ausentes. La clave antigua `jetskiStateSync.agentManagerInitState` también estaba ausente.

## Verificación

Se compararon los nombres y contenidos de los archivos de `extensions/`, `brain/`, `conversations/`, `settings.json` y las bases de `workspaceStorage/`. Se preservaron los respaldos anteriores. Todas las filas conservadas coincidieron con las copias verificadas. Entre ellas estaban `google.antigravity` donde existía y `antigravityUnifiedStateSync.trajectorySummaries` en ambas bases. La comprobación `PRAGMA integrity_check;` devolvió `ok` en las dos.

## Otras instalaciones

| Sistema | Ubicaciones candidatas de datos | Llavero |
|---|---|---|
| Windows | `%APPDATA%` y `%LOCALAPPDATA%` | `cmdkey` para un destino exacto |
| macOS | `~/Library/Application Support` y `~/Library/Caches` | `security` con servicio, cuenta y llavero comprobados |
| Linux | `XDG_CONFIG_HOME` o `~/.config`, y `XDG_CACHE_HOME` o `~/.cache` | `secret-tool` si el escritorio usa un servicio compatible |

En cada sistema hay que comprobar `Antigravity`, `agy`, el `language_server` y el navegador interno. La herramienta pública incluye la clave antigua solo si existe y deja `antigravity-acp/` para inspección manual. La confirmación del usuario corresponde a Windows; las rutas para otros sistemas requieren validación local.

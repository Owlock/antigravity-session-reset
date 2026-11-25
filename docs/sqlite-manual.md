# SQLite: manual edit and recovery / Edición manual y recuperación

SQLite stores the application's state in a file. A transaction lets you cancel a group of changes before you confirm them. SQLite guarda el estado de la aplicación en un archivo. Una transacción permite cancelar un grupo de cambios antes de confirmarlo.

1. Quit the application and verify the backup described in the README. Open a terminal in the correct app's `User/globalStorage`. In Windows File Explorer, type `cmd` in that folder's address bar. In macOS/Linux Terminal type `cd `, drag the folder into the window and press Enter. Run `dir state.vscdb` in Windows CMD or `ls -l ./state.vscdb` on macOS/Linux. Check that the file already exists. Run `sqlite3 --version`. If unavailable, use the Python script or stop.

   Cierra la aplicación y verifica el respaldo del README. Entra en `User/globalStorage` de la aplicación correcta. En Windows escribe `cmd` en la barra de dirección de la carpeta y pulsa Intro. En Terminal de macOS/Linux escribe `cd `, arrastra la carpeta a la ventana y pulsa Intro. Comprueba que `state.vscdb` existe y que tienes la herramienta `sqlite3` con los comandos anteriores.

2. Run `sqlite3 state.vscdb`. At `sqlite>` run this block. Record which protected names appear and require `ok` for integrity. An unexpected trigger is grounds to stop. Ejecuta el bloque en la consola de SQLite. Debe aparecer `ok` y la consulta de disparadores debe quedar vacía. Anota qué claves protegidas existen. Un disparador es una regla que puede modificar datos adicionales.

```sql
PRAGMA integrity_check;
SELECT name FROM sqlite_master WHERE type='trigger' AND lower(tbl_name)='itemtable';
SELECT key FROM ItemTable WHERE key IN
('google.antigravity','antigravityUnifiedStateSync.trajectorySummaries');
```

3. **Both main databases / Ambas bases principales.** Start a transaction and remove exact matches. The last key is from older releases; a missing key affects zero rows. Inicia una transacción y elimina solo estas coincidencias exactas. La última clave corresponde a versiones anteriores y se omite si está ausente.

```sql
BEGIN IMMEDIATE;
DELETE FROM ItemTable WHERE key COLLATE BINARY IN (
  'antigravityUnifiedStateSync.oauthToken',
  'antigravityUnifiedStateSync.userStatus',
  'antigravityUnifiedStateSync.modelCredits',
  'jetskiStateSync.agentManagerInitState'
);
```

4. **Antigravity only / Solo Antigravity.** Skip this block on Antigravity IDE. En Antigravity IDE pasa directamente al paso siguiente.

```sql
DELETE FROM ItemTable WHERE key COLLATE BINARY IN (
  'antigravityAuthStatus',
  'antigravityAnalytics.clearcutBuffer',
  'antigravityAnalytics.lastUploadTime',
  'antigravityOnboarding',
  'antigravityUnifiedStateSync.onboarding'
);
```

5. Repeat the checks from step 2. If `ok` and the same protected names appear, run `COMMIT;`, then `PRAGMA integrity_check;` and `.quit`. If anything fails before committing, use `ROLLBACK;` and `.quit`. Repite las comprobaciones. Si el resultado es correcto, confirma el cambio, vuelve a comprobar la integridad y sal. Ante un error anterior a la confirmación, cancela la transacción.

## Recover missing rows / Recuperar filas ausentes

Close the app, back up its **current** state and open the current main database as above. Attach the matching verified backup from the same application. Replace the example path locally. Use forward slashes when entering a Windows path inside SQLite. Cierra la aplicación, respalda su estado **actual** y abre la base actual. Sustituye la ruta de ejemplo por la copia verificada de la **misma aplicación**.

```sql
ATTACH DATABASE 'PATH/TO/VERIFIED/state.vscdb' AS saved;
PRAGMA saved.integrity_check;
```

After `ok`, use the exact name of a missing row you intend to recover. Repeat the `INSERT` only for other approved names you wish to restore. An existing row from a new account keeps its current value. Tras `ok`, usa el nombre exacto de cada fila ausente que quieras recuperar. Recuperar información de acceso puede volver a introducir la cuenta vieja.

```sql
BEGIN IMMEDIATE;
INSERT INTO main.ItemTable(key,value)
SELECT s.key,s.value FROM saved.ItemTable AS s
WHERE s.key COLLATE BINARY = 'antigravityUnifiedStateSync.userStatus'
  AND NOT EXISTS (SELECT 1 FROM main.ItemTable AS m WHERE m.key=s.key);
PRAGMA main.integrity_check;
```

If `ok`, enter `COMMIT;`, `DETACH DATABASE saved;`, then `.quit`. On an error before commit, use `ROLLBACK;`. Si aparece `ok`, confirma, desconecta la copia y sal. Si hay un error anterior a `COMMIT;`, cancela la transacción.

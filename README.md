# antigravity-session-reset

[Español](README.es.md) · [Manual SQLite guide](docs/sqlite-manual.md) · [Anonymized Windows case](docs/case-study.es.md)

A local tool and manual guide for switching Google accounts in Antigravity. Start here if the previous account reappears, sign-in loops, or the app displays Free after you select an email with an active Pro subscription. First verify which email owns the subscription at Google. Entitlements are controlled by Google.

One Windows user confirmed a fresh sign-in with chats, artifacts, extensions and settings preserved. The Python implementation has also been tested with disposable Windows fixtures. Native macOS and Linux end-to-end testing is pending.

## What changes

| Target | Action |
|---|---|
| Main `User/globalStorage/state.vscdb` | Delete exact approved rows present in the database. Preserve every other row, including `google.antigravity` and `antigravityUnifiedStateSync.trajectorySummaries`. |
| Both apps | Select `antigravityUnifiedStateSync.oauthToken`, `antigravityUnifiedStateSync.userStatus` and `antigravityUnifiedStateSync.modelCredits`. Older releases may also have `jetskiStateSync.agentManagerInitState`. Remove that legacy row only when present. |
| Antigravity only | Also select `antigravityAuthStatus`, `antigravityAnalytics.clearcutBuffer`, `antigravityAnalytics.lastUploadTime`, `antigravityOnboarding` and `antigravityUnifiedStateSync.onboarding`. These include analytics and welcome state. |
| App web data | Back up and remove the direct child directories `Cache`, `Code Cache`, `Network`, `Session Storage` and `Local Storage`. These may hold web interface preferences. |
| Local credentials | Select the exact Windows generic credential `gemini:antigravity` and the file `~/.gemini/jetski-standalone-oauth-token` if present. On macOS/Linux select the old vault item manually. |
| Internal browser | `--include-browser-profile` opts into backing up and removing `~/.gemini/antigravity-browser-profile/`, including its own settings and cookies. |
| Personal data | Preserve `extensions/`, `brain/`, `conversations/`, keybindings, settings, project databases and existing backups. Flag `~/.gemini/antigravity-acp/` for manual review. Its contents can vary. |

Here `~` means your home directory, including on Windows. Use the reset before signing in with the new account: app session stores are shared by the local app profile.

## Manual procedure

1. **Quit the app.** Save your work. Quit both Antigravity variants, `agy`, and the internal browser. In Windows press **Ctrl+Shift+Esc → Details**. On macOS use **Command+Space → Activity Monitor**. On Linux use your desktop's **System Monitor** or run `ps -A -o comm=` in Terminal. Check for Antigravity, `agy` and its `language_server`. A server may belong to another editor. Identify it before closing anything.
2. **Locate the data roots.** In Windows File Explorer press **Alt+D**, type `%APPDATA%` and press Enter. Repeat with `%LOCALAPPDATA%`. In macOS Finder choose **Go → Go to Folder** and check `~/Library/Application Support` and `~/Library/Caches`. In Linux use **Ctrl+L** in your file manager and check `~/.config` and `~/.cache`, or your configured `XDG_CONFIG_HOME` and `XDG_CACHE_HOME`. Look for `Antigravity` and `Antigravity IDE` directly inside those roots. Skip absent paths. Portable or sandboxed installs may differ.
3. **Make a private backup.** Outside app data, cloud sync and Git, create a timestamped folder. Preserve each source's relative path. Under each app inspect only `User/settings.json`, `User/globalStorage/state.vscdb` and `User/workspaceStorage/*/state.vscdb`; the star means a single project directory. Copy those files and all other targets you intend to remove. Verify nonzero sizes for settings and databases and compare the originals and copies using SHA-256 (a fingerprint of the bytes). For one file run `Get-FileHash -LiteralPath 'FILE'` in PowerShell, `shasum -a 256 "FILE"` in macOS Terminal, or `sha256sum "FILE"` in Linux Terminal. Substitute the original path, then the copy. Both results must match. Database companions named `-wal`, `-shm` or `-journal` can contain pending transactions. Keep them and stop until the app shuts down cleanly.
4. **Edit only the two main databases.** Follow the [manual SQLite steps](docs/sqlite-manual.md) separately for each existing app. The guide supplies the exact keys, a transaction, integrity checks and selective recovery. Skip the Antigravity-only statement when editing Antigravity IDE.
5. **Clear the selected local storage.** In each identified app root move the five web directories in the table to Trash. Keep `User/`. Under `~/.gemini` remove the exact standalone token file if present. Clear the internal browser only if you backed up its full profile and want its data reset. Leave `antigravity-acp/` in place if its contents are uncertain.
6. **Remove the old vault item.** Use your normal OS account:
   - **Windows:** press **Windows+R**, type `cmd` and press Enter. Run `cmdkey /list:gemini:antigravity`. If that is the intended credential, run `cmdkey /delete:gemini:antigravity`. Run the first command again to check.
   - **macOS:** use Spotlight to open **Keychain Access**. Search for `Antigravity`, verify service, account and keychain, and remove the individual item. The native equivalent is `security delete-generic-password -s "${AG_SERVICE:?}" -a "${AG_ACCOUNT:?}" "${AG_KEYCHAIN:?}"` after assigning all three verified values locally.
   - **Linux:** open **Passwords and Keys** from your applications, or type `seahorse` in Terminal if installed. Inspect the attributes and remove the individual item. With Secret Service, the equivalent is `secret-tool clear "${AG_KEY1:?}" "${AG_VALUE1:?}" "${AG_KEY2:?}" "${AG_VALUE2:?}"`. Use verified attribute/value pairs that together match just one item: all unlocked matches can be removed. Other desktops have different vault managers. If prompted, unlock the vault normally.
7. **Finish in the external browser.** Check the email in the old Google account's avatar menu. Open [Google connections](https://myaccount.google.com/connections), select Antigravity if listed, open its details and revoke access. In Chrome choose **Settings → Privacy and security → Third-party cookies → See all site data and permissions**. Search for `antigravity.google` and delete only its site data. Open a private window or separate browser profile. Start Antigravity and select sign-in. If it launches a normal tab, open that sign-in address in the isolated window and verify the new email before accepting. Keep the sign-in URL private.
8. **Verify before discarding backups.** Check the email and plan, open a previous conversation and artifact, and check extensions and preferences. If Google itself lists the wrong plan for that email, resolve the subscription there before repeating a reset.

## Automated use

Python 3.10+ with SQLite and the standard library. Use an ordinary terminal in the repository directory. On Windows use `py -3` or `python` if that is your installed launcher.

```sh
python3 -B ag_session_reset.py
python3 -B ag_session_reset.py --dry-run --include-browser-profile
python3 -B ag_session_reset.py --apply --include-browser-profile
```

The first two commands are read-only previews. `--apply` authorizes changes. Omit `--include-browser-profile` to keep the internal browser. `--backup-dir "PATH"` sets a private local parent for timestamped backups. The default is `~/.ag-session-backups/`. Subdirectories such as `roaming/`, `support/`, `config/`, `cache/` and `gemini/` identify the original locations.

The script checks running processes and reports only the blocking executable's name. It validates normalized removal paths before editing databases. Its targeted `User/` inspection skips linked workspace directories and avoids unrelated extension data. Selected linked files, unsettled databases or unexpected file types stop the run. A missing OS process-inspection tool also stops it.

Databases, settings and the token undergo two size/SHA-256 checks: source-to-copy verification while copying, then independent source and backup verification before edits. For web directories and the internal browser, each payload is read once from the source and once from the backup. Subsequent checks compare names, types and file metadata. Do not restart the app during the reset. Windows read-only cache files are retried locally. Each edited database is committed separately after checking all retained rows and `PRAGMA integrity_check;`. The vault step comes last.

## Recovery and privacy

If an error occurs after backup verification, keep the **first verified backup** and leave the app closed. Earlier edits may already have committed. Restore a needed folder from its matching backup location. For database entries use the [selective recovery procedure](docs/sqlite-manual.md). Sign in again to recreate a vault entry. If an interruption leaves `~/.ag-session-reset.lock/`, check your process manager for another Python run of `ag_session_reset.py`. Remove only that empty lock folder once you have confirmed no reset is active.

Backups may contain reusable sign-in data. After verifying the new login and personal data, delete any backup you no longer need and empty Trash as appropriate. Keep databases, vault listings, sign-in URLs and account details out of issues.

## Testing

From the repository folder run `python3 -B -m unittest discover -s tests -v`. The suite builds disposable profiles, uses an in-memory vault substitute, blocks native credential access and removes its temporary directories. The Windows 3.10 and 3.12 paths exercise both cache removal callbacks. A native macOS or Linux run is still needed before claiming platform validation.

Community-maintained; independent of Google. [MIT license](LICENSE).

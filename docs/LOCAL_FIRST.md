# 100% Local-First & Offline Guide

OpenMemory is designed from the ground up to be **Local-First**. You do **not** need a server, Docker, or any network connection to use it.

---

## 1. Zero-Server Operation

When running in **Local Mode**:
- All operations read and write directly to an embedded SQLite WAL database.
- Default database location: `~/.openmemory/memory.db`.
- Can be customized with the environment variable:
  ```bash
  export OPENMEMORY_DATA_DIR="/path/to/your/custom/storage"
  ```
- Instant sub-millisecond response latency.
- Full offline privacy: zero telemetry, zero background network pings.

---

## 2. Syncing via Obsidian / Git Markdown Vault

If you use multiple laptops or want human-readable backups without maintaining a 24/7 server, you can export your memories to an Obsidian or Git vault:

### Export to Markdown Vault:
```bash
python client/export_import.py export --format vault -o ./my_memory_vault
```
This generates a folder with:
- `README.md`: Index catalogue of active, conflicted, and pinned memories.
- Individual Markdown files organized by topic (e.g. `preference_*.md`, `architecture_*.md`).
- Standard YAML frontmatter (`id`, `category`, `confidence`, `sensitivity`, `source_type`).

### Sync across machines:
- Place `./my_memory_vault` inside your **Obsidian Vault**, **iCloud**, **OneDrive**, **Dropbox**, or a **Private Git Repository**.
- Edit or audit memories in your favorite Markdown editor.

---

## 3. Portable JSON Backup & Migration

Export an encrypted or plain JSON bundle:
```bash
# Export
python client/export_import.py export --format json -o ./backup.json

# Import into another machine
python client/export_import.py import -f ./backup.json
```

# Minecraft TU75 / Aurora database repair (Xbox 360 RGH/JTAG)

This fix addresses a long standing issue with getting the latest Minecraft title update (TU75) to launch correctly through Aurora. The fix is a simple database entry that can either be done with the provided python script or amended by hand through a database editor such as DB Browser

## Quick instructions (Linux / Windows / macOS)

1. **Make sure your own Minecraft TU75 package is installed/cached.** This utility **does not provide or download title updates**. Its expected package is `tu00000001_00000000` (approximately 1,352,560,640 bytes), SHA-1 `134378DAA5728AEC36BC0A8777857D0E9CA6D17B`. If that package is missing from Aurora's hashed update-cache folder, fixing the database alone will not work.
2. On the Xbox, **exit Minecraft**. Use FTP to **download** `Aurora/Data/Databases/content.db` to your PC. Your Aurora folder may be elsewhere, e.g. `Usb0/Aurora`.
3. **Back up** the downloaded original database in another location. Never use someone else's database; it contains their console's game and storage records.
4. Put `fix_minecraft_tu75.py` in the same folder as the downloaded `content.db`.
5. Preview the repair:
   ```sh
   python3 fix_minecraft_tu75.py content.db
   ```
6. If the preview matches the problem, generate a **new** database:
   ```sh
   python3 fix_minecraft_tu75.py content.db --fix
   ```
   Output: `content_tu75_fixed.db`. It **never overwrites** the original. Python 3 is required; no other packages.
7. Copy `content_tu75_fixed.db` to `Hdd1:/Temp/` on the Xbox via FTP and rename it to `content.db`.
8. **Close Aurora completely** by launching **XeXMenu**. Copy `Hdd1:/Temp/content.db` into the database directory. **Do not replace the live database while Aurora is running.**
9. Relaunch Aurora, select Minecraft → **Title Updates** → enable Version **80** (TU75), then launch Minecraft and check the active TU number via the Xbox Guide.
10. If Aurora does not show TU75 in the installed title updates section force Aurora to rescan for title updates to make it populate. If it still does not populate, check that you still actively have a TU75 file downloaded at `Hdd1/Aurora/Data/TitleUpdates/DriveID/584111F7/000B000/`

**If it fails:** Close Aurora and restore your original `content.db` from the backup. Do not delete the game, save files, or your TU cache. If you encounter a different record format, this tool intentionally refuses to make changes.

## What this repairs (technical)

- Game Title ID: `584111F7` (decimal `1480659447`)
- Media ID (tested): `7CD33B56`
- Aurora internal Title Update version: `80` (Minecraft **TU75**)
- File: `tu00000001_00000000`
- SHA-1 catalog hash: `134378DAA5728AEC36BC0A8777857D0E9CA6D17B`
- Active TU path: `\Content\0000000000000000\584111F7\000B0000\`
- Cached copy path: `Game:\Data\TitleUpdates\<drive-serial>\584111F7\<hash>\<filename>`

The script finds the **one** Version 80 row that points to the normal `000B0000` location, builds its `BackupPath` using the **row's own LiveDeviceId**, and deletes only extra matching Version 80 rows incorrectly pointing to `\Cache\` with blank BackupPath. It does not touch other titles or other update versions, and refuses unfamiliar schemas, hashes, or entries. If your Aurora database uses different details, **do not force the script**.

> **Note:** Old-style uppercase `TU_...` updates normally use `Hdd1:\Cache\`; lowercase `tu...` packages normally use `000B0000`. TU75 **is not supposed to generate an uppercase cache file**. The issue fixed here is Aurora's management metadata.


License: MIT. **No warranty. Backup before use.**

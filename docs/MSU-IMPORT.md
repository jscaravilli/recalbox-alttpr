# Import user-owned MSU-1 music

The console can import MSU-1 packs that a user legally owns. This project does
not provide, upload, or redistribute copyrighted music.

![Manage MSU Music screen](images/manage-msu-music.png)

## Import from another computer

Open the Recalbox SHARE network folder:

```text
Windows:  \\recalbox\share\import\msu
macOS:    smb://recalbox/share/import/msu
Linux:    smb://recalbox/share/import/msu
```

Copy exactly one pack into each folder or archive. Accepted inputs:

- extracted directory
- ZIP
- 7Z
- RAR

A pack must contain one consistently named numbered PCM set:

```text
My Soundtrack/
├── music.msu          # optional; an empty marker is created if absent
├── music-1.pcm
├── music-2.pcm
├── music-3.pcm
└── ...
```

Track numbers do not need to be consecutive, but each number must be unique.
Files from multiple differently named PCM sets must be separated into different
inputs.

On the television:

1. Open the **ALTTPR** system.
2. Select **Manage MSU Music**.
3. Select **Import Drop Folder**.
4. Wait for validation and copying to complete.
5. Return to **Generate Custom Seed** and choose the new `User:` pack under
   **MSU Music Pack**.

Successful source folders/archives move to:

```text
SHARE/import/msu/processed
```

This prevents repeated imports and keeps the original package available for
inspection. It can be deleted from the network share after the installed pack
has been tested.

## Validation and safety

The importer:

- rejects archive path traversal and symbolic links;
- rejects empty PCM tracks, duplicate track numbers, and mixed PCM sets;
- checks staging and installation disk space with a 64 MiB safety margin;
- installs into a temporary directory and switches it into place atomically;
- namespaces user packs with `user-` so curated updates cannot overwrite them;
- leaves failed inputs in the drop folder;
- rebuilds the runtime manifest only after a successful installation.

ZIP extraction uses Python’s checked archive reader. 7Z and RAR extraction uses
the same pinned ARM64 7-Zip binary as the curated installer.

## Remove an imported pack

Open **Manage MSU Music**, highlight a `User:` row, and press A/B twice.
Only user-imported packs can be removed from this screen. Curated packs and the
original SNES soundtrack are protected.

Removing a pack does not modify existing ROMs. Existing seeds may retain broken
symlinks to the removed music and will fall back according to emulator behavior;
choose **Default** or another installed pack for future seeds.

## Command-line operations

The television UI calls the same commands:

```sh
# Show pending inputs
python3 /recalbox/share/alttpr/bin/alttpr-msu-import.py --scan

# Import all pending inputs
python3 /recalbox/share/alttpr/bin/alttpr-msu-import.py --import-all

# List user packs
python3 /recalbox/share/alttpr/bin/alttpr-msu-import.py --list-user

# Delete a user pack by internal slug
python3 /recalbox/share/alttpr/bin/alttpr-msu-import.py \
  --delete user-my-soundtrack
```

Use `--replace` with `--import-all` only when intentionally replacing an
existing user pack with another input of the same name.

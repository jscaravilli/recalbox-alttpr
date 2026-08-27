# Troubleshooting

Start with the built-in health check:

```sh
ssh root@recalbox.local \
  /recalbox/share/alttpr/bin/alttpr-healthcheck.sh
```

Every required check should report `PASS`.

## ALTTPR does not appear in EmulationStation

Run the persistent installer and restart EmulationStation:

```sh
ssh root@recalbox.local \
  "bash /recalbox/share/alttpr/es/alttpr-install.sh && reboot"
```

## A seed does not generate

The generation screen reports the final engine error. Common causes:

- an unsupported Entrance Shuffle and legacy Overworld Shuffle combination;
- insufficient free space;
- an upstream layout that exhausted five automatic retries;
- a Stopwatch reservation/provenance check that intentionally failed closed.

Do not bypass a Stopwatch reservation error. Reinstall the pinned engine using
the update procedure in [INSTALL.md](INSTALL.md).

## A generated game has no sound

Confirm the television and Recalbox menu have audio, then rerun the installer.
The ALTTPR adapter supplies the PulseAudio runtime path required by nested SNES
launches.

## The tracker page does not load

1. Confirm the phone/tablet/computer is on the same network.
2. Try the Pi’s IP address:
   `http://PI-IP:8080/itemtracker.html`.
3. Reboot once.
4. Run the health check and confirm ports `8080` and `23074` pass.

The tracker shows `running: false` when no ALTTPR seed is active; that is normal.

## An imported MSU pack is rejected

Each input must contain one numbered PCM set such as `music-1.pcm`,
`music-2.pcm`, and so on. Separate differently named sets into different
folders/archives. Failed inputs remain in `SHARE/import/msu`.

See [MSU-IMPORT.md](MSU-IMPORT.md).

## A game exits but EmulationStation seems delayed

Wait up to 15 seconds for the bounded durability flush. The endgame hook never
restarts EmulationStation and never performs an unbounded `sync`.

## Known issues and resolved defects

See [BUGS-AND-FIXES.md](BUGS-AND-FIXES.md) for the Stopwatch, former Dark Cross,
and stochastic entrance-generation investigations.

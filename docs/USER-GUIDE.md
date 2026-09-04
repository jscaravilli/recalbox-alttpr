# User guide

Once installed, everything needed for normal play is available from the
**ALTTPR** system in EmulationStation.

## Generate and play a seed

1. Open **ALTTPR**.
2. Select **Generate Custom Seed**.
3. Move with the D-pad and change values with Left/Right.
4. Use L/R to move quickly through long lists such as character sprites.
5. Highlight **Generate & Play** and press A or B.

![Controller-driven seed configuration](images/generate-custom-seed.png)

The menu contains 67 options organized into:

- Seed Rules
- Items & Progression
- Entrance Randomizer
- Dungeon Door Randomizer
- Overworld & Flute
- Dungeon Items
- Enemies & Bosses
- Advanced Gameplay
- Cosmetics & Output

Every value has contextual help in the right-hand panel.

## Choose a character sprite

The console includes the official ALTTPR sprite library. Selecting **Link
Sprite** shows the character, name, and author before generation.

![Sprite picker with preview](images/sprite-picker.png)

Sprites are cosmetic and do not change game logic.

## Use the live tracker

Open the tracker from any device on the same network:

```text
http://recalbox.local:8080/itemtracker.html
```

The URL is permanent. It follows whichever ALTTPR seed is currently running and
shows the seed name, goal, timer, collected items, dungeon prizes, and remaining
checks.

![Items updating from live game memory](images/live-autotracker.gif)

Use **INV** and **MAP** in the bottom toolbar to switch views. Drag the map with
one finger and pinch with two fingers to zoom. Use **-** and **+** to resize the
inventory. The Broadcast View has separate inventory zoom controls.

No spoiler log is required. The bridge reads game memory but does not write to
it.

## Use the HUD Stopwatch

Set **HUD Timer** to **stopwatch** before generation. The timer appears in the
game HUD and counts upward throughout the run.

![HUD Stopwatch](images/hud-stopwatch.gif)

The console applies its guarded Stopwatch compatibility patch automatically.

## Adjust the low-health alert

Use **Heart Speed** when generating a custom seed to control the low-health
alert. **half** is the default. You can also select **normal**, **double**,
**quarter**, or **off**.

## Add your own MSU-1 music

Copy a legally owned extracted pack, ZIP, 7Z, or RAR into:

```text
SHARE/import/msu
```

Then select **Manage MSU Music** and **Import Drop Folder**. The pack appears as
a `User:` choice in the seed menu.

![Manage MSU Music](images/manage-msu-music.png)

See [MSU-IMPORT.md](MSU-IMPORT.md) for pack format and removal instructions.

## Replay a generated seed

Generated ROMs appear under the **SEEDS** folder. Select one to replay it.
SRAM is retained in Recalbox’s normal SNES save directory.

## View a spoiler log

When **Spoiler Log** was enabled during generation, select **View Spoiler Logs**
to browse item locations by region using the controller.

![On-TV spoiler viewer](images/spoiler-viewer.png)

## Clean old seeds

Select **Clean Old Seeds**, choose an age range, and confirm deletion. This
removes generated ROMs and their attached music links; saved games are kept.

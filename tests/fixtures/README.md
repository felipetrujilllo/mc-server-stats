# Test fixtures (fake data)

Made-up players only. Real server data must never be committed.
The layout mirrors the real server dir, so code can use `MC_SERVER_DIR=tests/fixtures`.

| Player | UUID | Role in tests |
|---|---|---|
| CraftyOtter | `3f9c2a71-8d4e-4b6a-9c15-7e2d0b8a4f63` | Veteran: most play time, 7 deaths, has `killed`, `killed_by`, `mined`. 5 real advancements, 2 recipe entries, 1 `done: false` partial (`adventuring_time`). Top slayer of zombie and creeper. |
| PixelMoth | `a12e7c09-5b3f-4d81-8e6a-2c9f41d7b0e5` | Mid player: top slayer of skeleton and spider. Exactly **2** real done advancements, **5** `minecraft:recipes/...` entries, 1 partial (`kill_all_mobs`). |
| NewbieNova | `6d0b4e92-1a7c-4f3e-b258-9e81c3a5d7f0` | Brand new: small `minecraft:custom` only. No `killed`, `killed_by` or `mined` (missing means zero). Advancements file has one recipe entry. |

If you change these numbers, update `tests/test_fixtures.py` and any tests that depend on them.

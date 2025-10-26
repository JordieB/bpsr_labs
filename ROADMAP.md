# BPSR Labs Roadmap

This document tracks larger follow-up tasks and research avenues that extend
past the immediate decoding effort.

## Data asset maintenance

- **Automate Star Resonance data refreshes.** Wire up a repeatable workflow for
  extracting the latest item definitions (e.g. via PotRooms miner updates) and
  pipe the results through `tools/update_item_mapping.py` so the repository's
  static `item_name_map.json` stays in sync with upstream game patches.


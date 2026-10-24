# Contributing to TalonSync

Thank you for helping! Bug reports, ideas and pull requests are all welcome.

## Before you start

- Open an issue first for anything big, so we can agree on it before you spend time on it.
- Keep changes focused: one fix or feature per pull request.
- Run the tests: `python tests/test_basic.py`, `python tests/test_library.py`, `python tests/test_enhanced.py`
  (and the other files in `tests/`). They need no VRChat and no network.
- New BASIC programs for the Program Library go in `talonsync/library.py`; every PRINT must fit in 30 columns, and
  `tests/test_library.py` must still run them all.

## Your contribution and the licence

TalonSync is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE.md). By sending a contribution
(a pull request, patch, program or other material) you agree that:

1. You wrote it, or otherwise have the right to give it to the project.
2. Everyone may use your contribution under the project's licence, like the rest of TalonSync.
3. NevvyDrone may also use, change, relicense and sell your contribution, as part of TalonSync, Talon Pilot or other
   NevvyDrone products, without paying you. You keep the copyright in your own work.

If you don't agree, please don't send the contribution. Credit for contributions is kept in the git history.

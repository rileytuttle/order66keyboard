# marbastlib (vendored)

Vendored subset of https://github.com/ebastler/marbastlib — CERN-OHL-P-2.0 (see LICENSE).

Kept: the `choc` and `various` symbol/footprint libraries. Everything else (mx, he,
hitek, gateron_lp, promicroish, and all the `xp-` experimental libraries) was dropped.

`3dmodels/` holds only the models referenced by footprints this project actually places.
If you start using another marbastlib footprint, re-fetch its model from upstream
`3dmodels/` — footprints look for it under
`${KICAD8_3RD_PARTY}/3dmodels/com_github_ebastler_marbastlib/`, which the project's
`fp-lib-table` does not define, so missing models are silently ignored by KiCad.

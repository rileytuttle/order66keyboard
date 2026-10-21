#!/usr/bin/env bash
# Run ERC against a throwaway KiCad config so the stock symbol/footprint libraries
# resolve without touching the user's ~/.config/kicad (which has no global tables
# until the GUI is launched once).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCH="$HERE/../pcb/order66-lp.kicad_sch"
SYMDIR="$(ls -d /nix/store/*kicad-symbols-*/share/kicad/symbols 2>/dev/null | head -1)"
FPDIR="$(ls -d /nix/store/*kicad-footprints-*/share/kicad/footprints 2>/dev/null | head -1)"
CFG="${ERC_CFG:-/tmp/order66lp-kicad-cfg}"
mkdir -p "$CFG/10.0"

{
  echo '(sym_lib_table'
  echo '  (version 7)'
  for f in "$SYMDIR"/*.kicad_sym; do
    n="$(basename "$f" .kicad_sym)"
    echo "  (lib (name \"$n\")(type \"KiCad\")(uri \"$f\")(options \"\")(descr \"\"))"
  done
  echo ')'
} > "$CFG/10.0/sym-lib-table"

{
  echo '(fp_lib_table'
  echo '  (version 7)'
  for d in "$FPDIR"/*.pretty; do
    n="$(basename "$d" .pretty)"
    echo "  (lib (name \"$n\")(type \"KiCad\")(uri \"$d\")(options \"\")(descr \"\"))"
  done
  echo ')'
} > "$CFG/10.0/fp-lib-table"

KICAD_CONFIG_HOME="$CFG" kicad-cli sch erc --severity-all -o /tmp/order66lp-erc.rpt "$SCH" || true
echo
echo "=== violations by type ==="
grep -oP '^\[\w+\]' /tmp/order66lp-erc.rpt | sort | uniq -c | sort -rn || echo "  none"

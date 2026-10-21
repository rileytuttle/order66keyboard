#!/usr/bin/env python3
"""
Smoke test: emit a one-symbol schematic for every part this design uses, and confirm
KiCad can load each one.

This exists because a malformed lib_symbols entry makes KiCad reject the entire file
with nothing but "Failed to load schematic" -- no line number, no indication of which
symbol. Run this first if the generated schematic stops loading, or after bumping a
vendored library, to find the offending part in one pass.

Run: python3 tools/smoke_symbols.py
"""
import sys, subprocess, os
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
from schlib import Sch

def run(name, build):
    s = Sch(paper='A3'); build(s)
    p=f'/tmp/bt_{name}.kicad_sch'; s.write(p)
    r=subprocess.run(['kicad-cli','sch','erc','--severity-all','-o',f'/tmp/bt_{name}.rpt',p],
                     capture_output=True,text=True,timeout=300)
    out=(r.stdout+r.stderr).strip()
    ok='Failed' not in out
    print(f'{name:22s} {"OK  " if ok else "FAIL"}  {out.splitlines()[-1][:70] if out else ""}')
    return ok

run('empty', lambda s: None)
run('text_only', lambda s: s.text('hello',(50,50)))
run('one_R', lambda s: s.symbol('Device:R','R1',(50,50),value='10k',footprint='Resistor_SMD:R_0402_1005Metric'))
run('one_diode', lambda s: s.symbol('Diode:1N4148WS','D1',(50,50),value='1N4148WS',footprint='Diode_SMD:D_SOD-323'))
run('one_choc', lambda s: s.symbol('marbastlib-choc:choc_v1_SW_HS_CPG135001S30','SW1',(50,50)))
run('one_led', lambda s: s.symbol('marbastlib-choc:choc_SK6812MINI-E','LED1',(50,50)))
run('one_nano', lambda s: s.symbol('nice_nano:nice_nano','U1',(80,80)))
run('one_eg', lambda s: s.symbol('EG1206A:EG1206A','SW62',(50,50)))
run('one_ss', lambda s: s.symbol('SSSS811101:SSSS811101','SW63',(50,50)))
run('one_hole', lambda s: s.symbol('Mechanical:MountingHole','H1',(50,50)))
run('one_tps', lambda s: s.symbol('Regulator_Switching:TPS61085DGK','U2',(80,80)))
run('one_125', lambda s: s.symbol('74xGxx:74AHCT1G125','U3',(80,80)))
run('one_fet', lambda s: s.symbol('Transistor_FET:AO3401A','Q1',(50,50)))
run('one_conn', lambda s: s.symbol('Connector:Conn_01x02_Pin','J1',(50,50)))
run('one_push', lambda s: s.symbol('Switch:SW_Push','SW61',(50,50)))
run('one_L', lambda s: s.symbol('Device:L','L1',(50,50)))
run('one_C', lambda s: s.symbol('Device:C','C1',(50,50)))
run('one_mbra', lambda s: s.symbol('Diode:MBRA340','D61',(50,50)))
def wl(s):
    s.symbol('Device:R','R1',(50,50),value='10k',footprint='x:y')
    s.stub('VCC', s.pin('Device:R',(50,50),1), 7.62, 'left')
run('R_with_stub', wl)
def nc(s):
    s.symbol('Device:R','R1',(50,50),value='10k',footprint='x:y')
    s.no_connect(s.pin('Device:R',(50,50),1))
run('R_with_nc', nc)

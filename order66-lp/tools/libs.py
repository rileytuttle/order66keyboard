"""Where each symbol library nickname lives, and pin-geometry extraction."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from sexpr import parse, get, getall, Str

STOCK = '/nix/store/42wzdgmf8rfix9j9wsa2ca9gb584a03m-kicad-symbols-a496b9e675/share/kicad/symbols'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VND = os.path.join(HERE, 'libraries')

LIBS = {
    'Switch': f'{STOCK}/Switch.kicad_sym',
    'Diode': f'{STOCK}/Diode.kicad_sym',
    'Device': f'{STOCK}/Device.kicad_sym',
    'Connector': f'{STOCK}/Connector.kicad_sym',
    'Mechanical': f'{STOCK}/Mechanical.kicad_sym',
    'Regulator_Switching': f'{STOCK}/Regulator_Switching.kicad_sym',
    'Transistor_FET': f'{STOCK}/Transistor_FET.kicad_sym',
    '74xGxx': f'{STOCK}/74xGxx.kicad_sym',
    'power': f'{STOCK}/power.kicad_sym',
    'marbastlib-choc': f'{VND}/marbastlib/symbols/marbastlib-choc.kicad_sym',
    'marbastlib-various': f'{VND}/marbastlib/symbols/marbastlib-various.kicad_sym',
    'nice_nano': f'{VND}/nice-nano-kicad/nice_nano.kicad_sym',
    'EG1206A': f'{VND}/EG1206A/KiCADv6/2025-06-18_12-05-45.kicad_sym',
    'SSSS811101': f'{VND}/SSSS811101/SSSS811101.kicad_sym',
}

_cache = {}


def _lib(nick):
    if nick not in _cache:
        root = parse(open(LIBS[nick]).read())[0]
        _cache[nick] = {str(s[1]): s for s in getall(root, 'symbol')}
    return _cache[nick]


def symbol_def(lib_id):
    """Return the parsed (symbol ...) node for 'Lib:Name'."""
    nick, name = lib_id.split(':', 1)
    d = _lib(nick)
    if name not in d:
        raise KeyError(f'{lib_id} not found; have e.g. {sorted(d)[:6]}')
    return d[name]


def base_def(lib_id):
    """Resolve (extends ...) so derived symbols yield the parent's graphics/pins."""
    nick, _ = lib_id.split(':', 1)
    sym = symbol_def(lib_id)
    seen = set()
    while True:
        ext = get(sym, 'extends')
        if not ext:
            return sym
        parent = str(ext[1])
        if parent in seen:
            return sym
        seen.add(parent)
        sym = symbol_def(f'{nick}:{parent}')


def pins(lib_id):
    """{pin_number: (x, y, angle, name, etype)} in symbol-local coordinates."""
    out = {}

    def walk(n):
        for c in n[1:]:
            if isinstance(c, list):
                if c[0] == 'pin':
                    at, num, nm = get(c, 'at'), get(c, 'number'), get(c, 'name')
                    if at and num:
                        out[str(num[1])] = (
                            float(at[1]), float(at[2]),
                            float(at[3]) if len(at) > 3 else 0.0,
                            str(nm[1]) if nm else '', str(c[1]),
                        )
                else:
                    walk(c)

    walk(base_def(lib_id))
    return out


def prop(lib_id, key, default=''):
    """Property from the symbol itself, falling back to the symbol it extends."""
    for node in (symbol_def(lib_id), base_def(lib_id)):
        for p in getall(node, 'property'):
            if str(p[1]) == key and str(p[2]):
                return str(p[2])
    return default


def resolved_symbol(lib_id):
    """
    Build the flattened (symbol "Lib:Name" ...) node for a schematic's lib_symbols
    cache: graphics and pins come from whatever the symbol extends, properties come
    from the symbol itself, and inner unit names are renamed to match.
    """
    import copy
    nick, name = lib_id.split(':', 1)
    derived = symbol_def(lib_id)
    base = base_def(lib_id)
    node = copy.deepcopy(base)
    node[1] = Str(lib_id)

    base_name = str(base[1])
    for child in node[1:]:
        if isinstance(child, list) and child and child[0] == 'symbol':
            inner = str(child[1])
            if inner.startswith(base_name):
                child[1] = Str(name + inner[len(base_name):])

    # Replace properties with the derived symbol's, keeping any the derived one omits.
    kept = [c for c in node[1:] if not (isinstance(c, list) and c and c[0] == 'property')]
    # kept[0] is the symbol name token; node[2:] is rebuilt below so it stays at index 1.
    props = {}
    for src in (base, derived):
        for p in getall(src, 'property'):
            key = str(p[1])
            if str(p[2]) or key not in props:
                props[key] = copy.deepcopy(p)
    node[2:] = list(props.values()) + kept[1:]
    return node

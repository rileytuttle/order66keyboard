"""Minimal s-expression reader/writer for KiCad files."""


def parse(text):
    """Parse one or more s-expressions; returns a list of nested lists/strings."""
    out, stack, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '(':
            node = []
            if stack:
                stack[-1].append(node)
            else:
                out.append(node)
            stack.append(node)
            i += 1
        elif c == ')':
            stack.pop()
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while text[j] != '"':
                if text[j] == '\\':
                    buf.append(text[j + 1])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            stack[-1].append(Str(''.join(buf)))
            i = j + 1
        elif c in ' \t\r\n':
            i += 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            stack[-1].append(text[i:j])
            i = j
    return out


class Str(str):
    """A token that was quoted in the source, so it must be re-quoted on write."""
    __slots__ = ()


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def dump(node, indent=0, tab='\t'):
    """Render a parsed node back to KiCad-style text."""
    if not isinstance(node, list):
        return q(node) if isinstance(node, Str) else str(node)
    pad = tab * indent
    head = node[0] if node else ''
    simple = all(not isinstance(c, list) for c in node[1:])
    if simple:
        parts = [dump(c) for c in node[1:]]
        return pad + '(' + str(head) + (' ' + ' '.join(parts) if parts else '') + ')'
    # Leading atoms stay on the head line (KiCad's own formatting).
    lead, rest = [], list(node[1:])
    while rest and not isinstance(rest[0], list):
        lead.append(dump(rest.pop(0)))
    first = pad + '(' + str(head) + (' ' + ' '.join(lead) if lead else '')
    lines = [first]
    for c in rest:
        if isinstance(c, list):
            lines.append(dump(c, indent + 1, tab))
        else:
            lines.append(tab * (indent + 1) + dump(c))
    lines.append(pad + ')')
    return '\n'.join(lines)


def get(node, key):
    """First direct child list whose head is `key`."""
    for c in node[1:]:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def getall(node, key):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == key]

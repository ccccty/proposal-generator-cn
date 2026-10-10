# -*- coding: utf-8 -*-
"""Simple LaTeX-to-OMML converter for engineering formulas."""
import re
from xml.etree import ElementTree as ET
NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

def el(tag, *children, **attrs):
    e = ET.Element("{%s}%s" % (NS, tag))
    for k, v in attrs.items():
        if v is not None: e.set(k, v)
    for c in children:
        if isinstance(c, str): e.append(mr(c))
        elif c is not None: e.append(c)
    return e

def mr(text):
    r = el("r"); t = el("t"); t.text = text
    t.set("xml:space", "preserve"); r.append(t)
    return r

# ----- Greek and operator maps -----
MAPS = {
    "\\alpha": "\u03b1", "\\beta": "\u03b2", "\\gamma": "\u03b3",
    "\\delta": "\u03b4", "\\theta": "\u03b8", "\\lambda": "\u03bb",
    "\\mu": "\u03bc", "\\pi": "\u03c0", "\\sigma": "\u03c3",
    "\\omega": "\u03c9", "\\phi": "\u03c6", "\\epsilon": "\u03b5",
    "\\Delta": "\u0394", "\\Sigma": "\u03a3", "\\Pi": "\u03a0",
    "\\Omega": "\u03a9", "\\Gamma": "\u0393",
    "\\times": "\u00d7", "\\cdot": "\u00b7", "\\leq": "\u2264",
    "\\geq": "\u2265", "\\approx": "\u2248", "\\neq": "\u2260",
    "\\pm": "\u00b1", "\\infty": "\u221e", "\\partial": "\u2202",
    "\\rightarrow": "\u2192", "\\Rightarrow": "\u21d2",
    "\\nabla": "\u2207", "\\propto": "\u221d",
}

def _apply_maps(text):
    for cmd in sorted(MAPS, key=len, reverse=True):
        text = text.replace(cmd, MAPS[cmd])
    return text

# ----- Core converter -----
def _parse_flat_expr(s):
    """Convert a flat LaTeX expression to list of (type, content) tokens.
    type can be: "text", "frac", "sqrt", "sup", "sub"
    """
    tokens = []
    i = 0
    buf = ""
    while i < len(s):
        c = s[i]
        # Check for \frac{...}{...}
        if s[i:i+6] == "\\frac" and i+6 < len(s) and s[i+6] == "{":
            if buf: tokens.append(("text", buf)); buf = ""
            # find num { } and den { }
            i += 7  # skip \frac{
            depth = 1; num = ""
            while i < len(s) and depth > 0:
                if s[i] == "{": depth += 1
                elif s[i] == "}": depth -= 1
                if depth > 0: num += s[i]
                i += 1
            if i < len(s) and s[i] == "{":
                i += 1; depth = 1; den = ""
                while i < len(s) and depth > 0:
                    if s[i] == "{": depth += 1
                    elif s[i] == "}": depth -= 1
                    if depth > 0: den += s[i]
                    i += 1
                tokens.append(("frac", num.strip(), den.strip()))
            continue
        # Check for \sqrt[n]{...}
        if s[i:i+5] == "\\sqrt" and i+5 < len(s):
            if buf: tokens.append(("text", buf)); buf = ""
            i += 5
            deg = ""
            if s[i] == "[":
                i += 1
                while i < len(s) and s[i] != "]":
                    deg += s[i]; i += 1
                i += 1  # skip ]
            if i < len(s) and s[i] == "{":
                i += 1; depth = 1; body = ""
                while i < len(s) and depth > 0:
                    if s[i] == "{": depth += 1
                    elif s[i] == "}": depth -= 1
                    if depth > 0: body += s[i]
                    i += 1
                tokens.append(("sqrt", deg.strip(), body.strip()))
            continue
        # Handle ^ and _
        if c in "^_" and i+1 < len(s):
            if buf: tokens.append(("text", buf)); buf = ""
            typ = "sup" if c == "^" else "sub"
            i += 1
            if s[i] == "{":
                i += 1; depth = 1; content = ""
                while i < len(s) and depth > 0:
                    if s[i] == "{": depth += 1
                    elif s[i] == "}": depth -= 1
                    if depth > 0: content += s[i]
                    i += 1
                tokens.append((typ, content.strip()))
            else:
                tokens.append((typ, s[i])); i += 1
            continue
        buf += c
        i += 1
    if buf: tokens.append(("text", buf))
    return tokens

def tokens_to_omml(toks):
    """Convert token list to oMath XML element."""
    om = el("oMath")
    for t in toks:
        if t[0] == "text":
            om.append(mr(_apply_maps(t[1])))
        elif t[0] == "frac":
            f = el("f")
            f.append(el("num", mr(_apply_maps(t[1] if t[1] else ""))))
            f.append(el("den", mr(_apply_maps(t[2] if t[2] else ""))))
            om.append(f)
        elif t[0] == "sqrt":
            rad = el("rad")
            if t[1]:
                rad.append(el("deg", mr(_apply_maps(t[1]))))
            body = t[2] if t[2] else ""
            rad.append(el("e", mr(_apply_maps(body))))
            om.append(rad)
        elif t[0] in ("sup", "sub"):
            tag = "sSup" if t[0] == "sup" else "sSub"
            inner_tag = "sup" if t[0] == "sup" else "sub"
            prev = om[-1] if len(om) > 0 else None
            if prev is not None:
                om.remove(prev)
                om.append(el(tag, el("e", prev), el(inner_tag, mr(_apply_maps(t[1])))))
            else:
                om.append(el(tag, el("e", mr("")), el(inner_tag, mr(_apply_maps(t[1])))))
    return om

def latex_to_omml(expr):
    if not expr or not expr.strip():
        return ""
    try:
        expr = expr.strip()
        # Handle \left( ... \right) — just strip them, keep parens
        expr = expr.replace("\\left(", "(").replace("\\right)", ")")
        expr = expr.replace("\\left[", "[").replace("\\right]", "]")
        toks = _parse_flat_expr(expr)
        om = tokens_to_omml(toks)
        return ET.tostring(om, encoding="unicode")
    except Exception as e:
        r = el("oMath"); r.append(mr("[ERR:%s]" % str(e)[:40]))
        return ET.tostring(r, encoding="unicode")

def latex_to_omml_para(expr):
    o = latex_to_omml(expr)
    if not o: return ""
    return '<m:oMathPara xmlns:m="%s">%s</m:oMathPara>' % (NS, o)

def latex_to_omml_inline(expr):
    return latex_to_omml(expr)

# ----- Markdown extraction -----
EQ_DISPLAY = re.compile(r"\$\$\s*(.+?)\s*\$\$", re.DOTALL)
EQ_INLINE  = re.compile(r"(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)")

def extract_equations(md):
    segs = []
    pos = 0
    for m in EQ_DISPLAY.finditer(md):
        if m.start() > pos: segs.append(("md", md[pos:m.start()]))
        segs.append(("display", m.group(1).strip()))
        pos = m.end()
    if pos < len(md):
        rem = md[pos:]
        pos2 = 0
        for m2 in EQ_INLINE.finditer(rem):
            if m2.start() > pos2: segs.append(("md", rem[pos2:m2.start()]))
            segs.append(("inline", m2.group(1).strip()))
            pos2 = m2.end()
        if pos2 < len(rem): segs.append(("md", rem[pos2:]))
    return segs

# -*- coding: utf-8 -*-
"""Simple LaTeX-to-OMML converter for engineering formulas."""
import re
from xml.etree import ElementTree as ET
NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("m", NS)
ET.register_namespace("w", WNS)

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

def _val_el(tag, val):
    """Element carrying an m:val attribute, e.g. <m:begChr m:val="("/>."""
    e = el(tag)
    e.set("{%s}val" % NS, val)
    return e

# ----- Greek and operator maps -----
MAPS = {
    "\\alpha": "\u03b1", "\\beta": "\u03b2", "\\gamma": "\u03b3",
    "\\delta": "\u03b4", "\\theta": "\u03b8", "\\lambda": "\u03bb",
    "\\mu": "\u03bc", "\\pi": "\u03c0", "\\sigma": "\u03c3",
    "\\omega": "\u03c9", "\\phi": "\u03c6", "\\epsilon": "\u03b5",
    "\\tau": "\u03c4", "\\rho": "\u03c1", "\\nu": "\u03bd",
    "\\kappa": "\u03ba", "\\chi": "\u03c7", "\\psi": "\u03c8",
    "\\zeta": "\u03b6", "\\eta": "\u03b7", "\\xi": "\u03be",
    "\\upsilon": "\u03c5",
    "\\Delta": "\u0394", "\\Sigma": "\u03a3", "\\Pi": "\u03a0",
    "\\Omega": "\u03a9", "\\Gamma": "\u0393", "\\Lambda": "\u039b",
    "\\Phi": "\u03a6", "\\Psi": "\u03a8", "\\Xi": "\u039e",
    "\\Theta": "\u0398", "\\Upsilon": "\u03a5",
    "\\times": "\u00d7", "\\cdot": "\u00b7", "\\leq": "\u2264",
    "\\geq": "\u2265", "\\approx": "\u2248", "\\neq": "\u2260",
    "\\pm": "\u00b1", "\\infty": "\u221e", "\\partial": "\u2202",
    "\\rightarrow": "\u2192", "\\Rightarrow": "\u21d2",
    "\\nabla": "\u2207", "\\propto": "\u221d",
    "\\{": "{", "\\}": "}",
}

# Function-name commands rendered upright (plain style), like \log / \sin.
FUNC_CMDS = ("\\arg", "\\max", "\\min", "\\log", "\\ln", "\\sin", "\\cos",
             "\\tan", "\\cot", "\\sec", "\\exp", "\\det", "\\lim", "\\sup",
             "\\inf", "\\gcd", "\\deg", "\\dim", "\\ker", "\\Pr")

# Characters that may directly follow \left (\right handled separately).
_DELIM_BEG = "([{|\\."
_DELIM_END = ")]}|\\."

def _apply_maps(text):
    for cmd in sorted(MAPS, key=len, reverse=True):
        text = text.replace(cmd, MAPS[cmd])
    return text

def _read_group(s, i):
    """s[i] must be '{'; return (content, index just past the matching '}')."""
    i += 1
    depth = 1
    out = []
    while i < len(s) and depth > 0:
        ch = s[i]
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                i += 1
                break
        out.append(ch)
        i += 1
    return "".join(out), i

def _read_delim_char(s, i):
    r"""Read one delimiter char after \left / \right; '.' maps to '' (invisible)."""
    if i >= len(s):
        return "", i
    if s[i] == "\\" and i + 1 < len(s):
        c2 = s[i + 1]
        if c2 == "{": return "{", i + 2
        if c2 == "}": return "}", i + 2
        if c2 == "|": return "\u2016", i + 2
        return c2, i + 2
    c = s[i]
    if c == ".":
        return "", i + 1
    return c, i + 1

# ----- Core converter -----
def _parse_flat_expr(s):
    """Convert a flat LaTeX expression to list of (type, ...) tokens.
    type can be: "text", "frac", "sqrt", "sup", "sub", "delim",
    "mathbf", "plain", "hat", "bar", "func"
    """
    tokens = []
    i = 0
    buf = ""
    while i < len(s):
        c = s[i]
        # Check for \frac{...}{...}
        if s[i:i+5] == "\\frac" and i+5 < len(s) and s[i+5] == "{":
            if buf: tokens.append(("text", buf)); buf = ""
            # find num { } and den { }
            i += 6  # skip \frac{
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
        # Check for \left<d> ... \right<d>  (paired delimiters -> m:d)
        if s[i:i+5] == "\\left" and i+5 < len(s) and s[i+5] in _DELIM_BEG:
            if buf: tokens.append(("text", buf)); buf = ""
            i += 5
            beg, i = _read_delim_char(s, i)
            depth = 1; j = i; end = -1
            while j < len(s):
                if s[j:j+5] == "\\left" and j+5 < len(s) and s[j+5] in _DELIM_BEG:
                    depth += 1; j += 5
                elif s[j:j+6] == "\\right" and j+6 < len(s) and s[j+6] in _DELIM_END:
                    depth -= 1
                    if depth == 0:
                        end = j; break
                    j += 6
                else:
                    j += 1
            if end < 0:  # no matching \right: emit literally
                tokens.append(("text", "\\left" + beg))
                continue
            inner = s[i:end]
            i = end + 6
            endchr, i = _read_delim_char(s, i)
            tokens.append(("delim", beg, endchr, inner))
            continue
        # Check for \| (double bar U+2016). A pair of them delimits a norm -> m:d.
        if s[i:i+2] == "\\|":
            if buf: tokens.append(("text", buf)); buf = ""
            nxt = s.find("\\|", i + 2)
            if nxt >= 0:
                tokens.append(("delim", "\u2016", "\u2016", s[i+2:nxt]))
                i = nxt + 2
            else:
                tokens.append(("text", "\u2016"))
                i += 2
            continue
        # Check for \qquad / \quad (full-width spacing)
        if s[i:i+6] == "\\qquad":
            if buf: tokens.append(("text", buf)); buf = ""
            tokens.append(("text", "\u3000\u3000")); i += 6
            continue
        if s[i:i+5] == "\\quad":
            if buf: tokens.append(("text", buf)); buf = ""
            tokens.append(("text", "\u3000")); i += 5
            continue
        # Check for group commands \mathbf \mathrm \text \hat \bar
        grp_typ = None
        for cmd, typ in (("\\mathbf", "mathbf"), ("\\mathrm", "plain"),
                         ("\\text", "plain"), ("\\hat", "hat"), ("\\bar", "bar")):
            if s[i:i+len(cmd)] == cmd:
                nxt = i + len(cmd)
                if nxt < len(s) and s[nxt].isalpha():
                    break  # a longer, unsupported command
                grp_typ = typ
                i = nxt
                break
        if grp_typ is not None:
            if buf: tokens.append(("text", buf)); buf = ""
            while i < len(s) and s[i] == " ": i += 1
            if i < len(s) and s[i] == "{":
                content, i = _read_group(s, i)
            elif i < len(s) and s[i] == "\\":
                k = i + 1
                while k < len(s) and s[k].isalpha(): k += 1
                if k == i + 1: k = min(k + 1, len(s))
                content = s[i:k]; i = k
            elif i < len(s):
                content = s[i]; i += 1
            else:
                content = ""
            tokens.append((grp_typ, content.strip()))
            continue
        # Check for function names (\arg \max \min \log \sin ...)
        func_hit = None
        for cmd in FUNC_CMDS:
            if s[i:i+len(cmd)] == cmd:
                nxt = i + len(cmd)
                if nxt < len(s) and s[nxt].isalpha():
                    continue
                func_hit = cmd
                break
        if func_hit is not None:
            if buf: tokens.append(("text", buf)); buf = ""
            tokens.append(("func", func_hit[1:]))
            i += len(func_hit)
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

def _styled_run(text, plain=False, bold=False):
    """Build one <m:r>; plain=True forces upright (m:sty p), bold=True adds w:b."""
    r = mr(_apply_maps(text))
    if bold:
        wrpr = ET.Element("{%s}rPr" % WNS)
        ET.SubElement(wrpr, "{%s}b" % WNS)
        r.insert(0, wrpr)
    if plain:
        mrpr = ET.Element("{%s}rPr" % NS)
        sty = ET.SubElement(mrpr, "{%s}sty" % NS)
        sty.set("{%s}val" % NS, "p")
        r.insert(1 if bold else 0, mrpr)
    return r

def _bold_runs(elem):
    """Add <w:rPr><w:b/></w:rPr> (and m:sty b) to every <m:r> in elem."""
    for r in elem.iter("{%s}r" % NS):
        if r.find("{%s}rPr" % WNS) is None:
            wrpr = ET.Element("{%s}rPr" % WNS)
            ET.SubElement(wrpr, "{%s}b" % WNS)
            r.insert(0, wrpr)
        mrpr = r.find("{%s}rPr" % NS)
        if mrpr is None:
            mrpr = ET.Element("{%s}rPr" % NS)
            r.insert(1, mrpr)  # after w:rPr, before m:t
        if mrpr.find("{%s}sty" % NS) is None:
            sty = ET.SubElement(mrpr, "{%s}sty" % NS)
            sty.set("{%s}val" % NS, "b")

def _plain_runs(elem):
    """Force every <m:r> in elem upright via <m:rPr><m:sty m:val="p"/></m:rPr>."""
    for r in elem.iter("{%s}r" % NS):
        mrpr = r.find("{%s}rPr" % NS)
        if mrpr is None:
            mrpr = ET.Element("{%s}rPr" % NS)
            idx = 1 if r.find("{%s}rPr" % WNS) is not None else 0
            r.insert(idx, mrpr)
        if mrpr.find("{%s}sty" % NS) is None:
            sty = ET.SubElement(mrpr, "{%s}sty" % NS)
            sty.set("{%s}val" % NS, "p")

def _build(toks):
    """Build a standalone oMath element from tokens (used for sub-expressions)."""
    om = el("oMath")
    _append_tokens(om, toks)
    return om

def _append_tokens(om, toks):
    """Append OMML children for the token list to parent element om."""
    for t in toks:
        typ = t[0]
        if typ == "text":
            om.append(mr(_apply_maps(t[1])))
        elif typ == "func":
            om.append(_styled_run(t[1], plain=True))
        elif typ == "frac":
            f = el("f")
            num = el("num"); _append_tokens(num, _parse_flat_expr(t[1] if t[1] else ""))
            den = el("den"); _append_tokens(den, _parse_flat_expr(t[2] if t[2] else ""))
            f.append(num); f.append(den)
            om.append(f)
        elif typ == "sqrt":
            rad = el("rad")
            if t[1]:
                deg = el("deg"); _append_tokens(deg, _parse_flat_expr(t[1]))
                rad.append(deg)
            body = t[2] if t[2] else ""
            e_el = el("e"); _append_tokens(e_el, _parse_flat_expr(body))
            rad.append(e_el)
            om.append(rad)
        elif typ == "delim":
            d = el("d")
            dPr = el("dPr")
            dPr.append(_val_el("begChr", t[1]))
            dPr.append(_val_el("endChr", t[2]))
            d.append(dPr)
            e_el = el("e"); _append_tokens(e_el, _parse_flat_expr(t[3]))
            d.append(e_el)
            om.append(d)
        elif typ == "mathbf":
            sub = _build(_parse_flat_expr(t[1]))
            _bold_runs(sub)
            for child in list(sub):
                om.append(child)
        elif typ == "plain":
            sub = _build(_parse_flat_expr(t[1]))
            _plain_runs(sub)
            for child in list(sub):
                om.append(child)
        elif typ == "hat":
            acc = el("acc")
            accPr = el("accPr")
            accPr.append(_val_el("chr", "\u0302"))
            acc.append(accPr)
            e_el = el("e"); _append_tokens(e_el, _parse_flat_expr(t[1]))
            acc.append(e_el)
            om.append(acc)
        elif typ == "bar":
            bar = el("bar")
            barPr = el("barPr")
            barPr.append(_val_el("pos", "top"))
            bar.append(barPr)
            e_el = el("e"); _append_tokens(e_el, _parse_flat_expr(t[1]))
            bar.append(e_el)
            om.append(bar)
        elif typ in ("sup", "sub"):
            tag = "sSup" if typ == "sup" else "sSub"
            inner_tag = "sup" if typ == "sup" else "sub"
            prev = om[-1] if len(om) > 0 else None
            e_el = el("e")
            if prev is not None:
                om.remove(prev)
                e_el.append(prev)
            sc = el(inner_tag)
            _append_tokens(sc, _parse_flat_expr(t[1]))
            om.append(el(tag, e_el, sc))

def tokens_to_omml(toks):
    """Convert token list to oMath XML element."""
    om = el("oMath")
    _append_tokens(om, toks)
    return om

def latex_to_omml(expr):
    if not expr or not expr.strip():
        return ""
    try:
        expr = expr.strip()
        toks = _parse_flat_expr(expr)
        om = tokens_to_omml(toks)
        return ET.tostring(om, encoding="unicode")
    except Exception as e:
        r = el("oMath"); r.append(mr("[ERR:%s]" % str(e)[:40]))
        return ET.tostring(r, encoding="unicode")

def latex_to_omml_para(expr):
    o = latex_to_omml(expr)
    if not o: return ""
    # Wrapper must declare xmlns:m itself: _insert_omml parses this string standalone,
    # and a bare <m:oMathPara> root with an undeclared m: prefix fails XML parsing.
    return '<m:oMathPara xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">%s</m:oMathPara>' % o

def latex_to_omml_inline(expr):
    return latex_to_omml(expr)

# ----- Markdown extraction -----
EQ_DISPLAY = re.compile(r"\$\$\s*(.+?)\s*\$\$", re.DOTALL)
EQ_INLINE  = re.compile(r"(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)")

EQ_ANY = re.compile(r"\$\$\s*(.+?)\s*\$\$|(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)", re.DOTALL)

def extract_equations(md):
    # Single-pass scan: inline formulas live in the prose BETWEEN display blocks,
    # so a display-first two-pass scan silently drops them all.
    segs = []
    pos = 0
    for m in EQ_ANY.finditer(md):
        if m.start() > pos: segs.append(("md", md[pos:m.start()]))
        if m.group(1) is not None:
            segs.append(("display", m.group(1).strip()))
        else:
            segs.append(("inline", m.group(2).strip()))
        pos = m.end()
    if pos < len(md): segs.append(("md", md[pos:]))
    return segs

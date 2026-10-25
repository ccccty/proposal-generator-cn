# -*- coding: utf-8 -*-
"""LaTeX -> OMML (Word native equation) converter for Chinese engineering proposals.

Design goals
------------
1. 输出真正的 Word 原生公式（m:oMath / m:oMathPara），不是图片、不是外挂对象。
2. 覆盖申报书研究内容章真实会用到的东西：分式、根式、上下标、希腊字母、
   定界符、求和/积分（n-ary）、向量/矩阵粗体、范数、重音（帽/横线/波浪/点）。
3. 不支持的写法必须"叫出来"：unknown_commands() 给出清单，md2docx.py --strict
   会据此失败，避免字面反斜杠静默进入交付件。

API（对 md2docx.py 稳定）
------------------------
latex_to_omml(expr) -> str
latex_to_omml_para(expr) -> str          # 独立行公式包装
latex_to_omml_inline(expr) -> str
extract_equations(md) -> [(kind, body)]
unknown_commands(expr) -> [str]           # 未识别的 LaTeX 命令
EQ_DISPLAY / EQ_INLINE / EQ_ANY
"""
import re
from xml.etree import ElementTree as ET

NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("m", NS)
ET.register_namespace("w", WNS)


def el(tag, *children, **attrs):
    e = ET.Element("{%s}%s" % (NS, tag))
    for k, v in attrs.items():
        if v is not None:
            e.set(k, v)
    for c in children:
        if isinstance(c, str):
            e.append(mr(c))
        elif c is not None:
            e.append(c)
    return e


def mr(text):
    r = el("r")
    t = el("t")
    t.text = text
    t.set("xml:space", "preserve")
    r.append(t)
    return r


def _val_el(tag, val):
    """Element carrying an m:val attribute, e.g. <m:begChr m:val="("/>."""
    e = el(tag)
    e.set("{%s}val" % NS, val)
    return e


# ----- Greek / operator symbol map -----
MAPS = {
    "\\alpha": "\u03b1", "\\beta": "\u03b2", "\\gamma": "\u03b3",
    "\\delta": "\u03b4", "\\theta": "\u03b8", "\\lambda": "\u03bb",
    "\\mu": "\u03bc", "\\pi": "\u03c0", "\\sigma": "\u03c3",
    "\\omega": "\u03c9", "\\phi": "\u03c6", "\\varphi": "\u03d5",
    "\\epsilon": "\u03b5", "\\varepsilon": "\u03b5",
    "\\tau": "\u03c4", "\\rho": "\u03c1", "\\nu": "\u03bd",
    "\\kappa": "\u03ba", "\\chi": "\u03c7", "\\psi": "\u03c8",
    "\\zeta": "\u03b6", "\\eta": "\u03b7", "\\xi": "\u03be",
    "\\iota": "\u03b9", "\\upsilon": "\u03c5",
    "\\Delta": "\u0394", "\\Sigma": "\u03a3", "\\Pi": "\u03a0",
    "\\Omega": "\u03a9", "\\Gamma": "\u0393", "\\Lambda": "\u039b",
    "\\Phi": "\u03a6", "\\Psi": "\u03a8", "\\Xi": "\u039e",
    "\\Theta": "\u0398", "\\Upsilon": "\u03a5",
    "\\times": "\u00d7", "\\cdot": "\u00b7", "\\div": "\u00f7",
    "\\leq": "\u2264", "\\le": "\u2264", "\\geq": "\u2265", "\\ge": "\u2265",
    "\\approx": "\u2248", "\\neq": "\u2260", "\\ne": "\u2260",
    "\\equiv": "\u2261", "\\sim": "\u223c", "\\simeq": "\u2243",
    "\\ll": "\u226a", "\\gg": "\u226b",
    "\\pm": "\u00b1", "\\mp": "\u2213",
    "\\infty": "\u221e", "\\partial": "\u2202", "\\nabla": "\u2207",
    "\\propto": "\u221d", "\\angle": "\u2220", "\\perp": "\u22a5",
    "\\parallel": "\u2225", "\\mid": "\u2223",
    "\\rightarrow": "\u2192", "\\to": "\u2192", "\\Rightarrow": "\u21d2",
    "\\leftarrow": "\u2190", "\\Leftarrow": "\u21d0",
    "\\leftrightarrow": "\u2194", "\\Leftrightarrow": "\u21d4",
    "\\uparrow": "\u2191", "\\downarrow": "\u2193",
    "\\in": "\u2208", "\\notin": "\u2209",
    "\\subset": "\u2282", "\\supset": "\u2283",
    "\\subseteq": "\u2286", "\\supseteq": "\u2287",
    "\\cup": "\u222a", "\\cap": "\u2229", "\\emptyset": "\u2205",
    "\\forall": "\u2200", "\\exists": "\u2203",
    "\\oplus": "\u2295", "\\otimes": "\u2297", "\\odot": "\u2299",
    "\\circ": "\u2218", "\\ast": "\u2217", "\\star": "\u22c6",
    "\\prime": "\u2032", "\\degree": "\u00b0",
    "\\cdots": "\u22ef", "\\ldots": "\u2026", "\\dots": "\u2026",
    "\\vdots": "\u22ee", "\\ddots": "\u22f1",
    "\\langle": "\u27e8", "\\rangle": "\u27e9",
    "\\{": "{", "\\}": "}", "\\%": "%", "\\&": "&", "\\#": "#",
    "\\_": "_", "\\$": "$", "\\ ": "\u00a0",
}

# Upright function names (\log, \max ... rendered in plain style)
FUNC_CMDS = ("\\arg", "\\max", "\\min", "\\log", "\\lg", "\\ln", "\\sin",
             "\\cos", "\\tan", "\\cot", "\\sec", "\\csc", "\\exp", "\\det",
             "\\lim", "\\sup", "\\inf", "\\gcd", "\\deg", "\\dim", "\\ker",
             "\\Pr", "\\mod")

# N-ary operators: command -> (glyph, limit location)
NARY = {
    "\\sum": ("\u2211", "undOvr"),
    "\\prod": ("\u220f", "undOvr"),
    "\\bigcup": ("\u22c3", "undOvr"),
    "\\bigcap": ("\u22c2", "undOvr"),
    "\\int": ("\u222b", "subSup"),
    "\\iint": ("\u222c", "subSup"),
    "\\iiint": ("\u222d", "subSup"),
    "\\oint": ("\u222e", "subSup"),
}

# Accent commands: command -> combining mark
ACCENTS = {
    "\\hat": "\u0302",
    "\\tilde": "\u0303",
    "\\vec": "\u20d7",
    "\\dot": "\u0307",
    "\\ddot": "\u0308",
}

# Group commands rendered with a special style.
GROUP_CMDS = (
    ("\\mathbf", "mathbf"),
    ("\\boldsymbol", "mathbf"),
    ("\\mathrm", "plain"),
    ("\\text", "plain"),
    ("\\operatorname", "operatorname"),
    ("\\bar", "bar"),
    ("\\ddot", "ddot"),
    ("\\dot", "dot"),
    ("\\tilde", "tilde"),
    ("\\vec", "vec"),
    ("\\hat", "hat"),
)

_DELIM_BEG = "([{|<\\."
_DELIM_END = ")]}|>\\."

STRUCTURAL_CMDS = {
    "\\frac", "\\dfrac", "\\tfrac", "\\sqrt", "\\left", "\\right",
    "\\quad", "\\qquad", "\\,", "\\;", "\\!", "\\%", "\\&", "\\#",
    "\\_", "\\$", "\\{", "\\}", "\\|", "\\\\",
}


def _apply_maps(text):
    for cmd in sorted(MAPS, key=len, reverse=True):
        text = text.replace(cmd, MAPS[cmd])
    return text


def _known_command_names():
    names = set()
    for k in list(MAPS) + list(NARY) + list(ACCENTS) + list(FUNC_CMDS) + list(STRUCTURAL_CMDS):
        names.add(k[1:])
    for cmd, _typ in GROUP_CMDS:
        names.add(cmd[1:])
    return names


KNOWN_COMMANDS = _known_command_names()


def unknown_commands(expr):
    """Return LaTeX commands in *expr* that this converter does not understand.

    Callers should treat a non-empty result as an error for deliverable
    documents: unknown commands are emitted as literal text (e.g. "\tilde{x}")
    instead of being silently dropped, so they would be visible to reviewers.
    """
    found = []
    for m in re.finditer(r"\\([A-Za-z]+)", expr or ""):
        name = m.group(1)
        if name not in KNOWN_COMMANDS:
            found.append("\\" + name)
    seen = []
    for c in found:
        if c not in seen:
            seen.append(c)
    return seen


def _read_group(s, i):
    """s[i] must be '{'; return (content, index just past the matching '}')."""
    i += 1
    depth = 1
    out = []
    while i < len(s) and depth > 0:
        ch = s[i]
        if ch == "{":
            depth += 1
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
        if c2 == "{":
            return "{", i + 2
        if c2 == "}":
            return "}", i + 2
        if c2 == "|":
            return "\u2016", i + 2
        return c2, i + 2
    c = s[i]
    if c == ".":
        return "", i + 1
    return c, i + 1


def _read_script(s, i):
    """Read one ^_ argument (group or single token). Return (content, i)."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return "", i
    if s[i] == "{":
        content, i = _read_group(s, i)
        return content.strip(), i
    if s[i] == "\\":
        j = i + 1
        if j < len(s) and s[j].isalpha():
            while j < len(s) and s[j].isalpha():
                j += 1
        else:
            j = min(j + 1, len(s))
        return s[i:j], j
    return s[i], i + 1


def _read_atom(s, i):
    r"""Read one LaTeX atom plus its attached scripts, as raw LaTeX text.

    Used as the operand of a n-ary operator (\sum, \int ...). Consuming the
    script suffixes here keeps \sum_{i} x_i grouped as x_i instead of letting
    the trailing _i rebind to the n-ary node.
    """
    start = i
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return "", i
    if s[i] == "{":
        body, i = _read_group(s, i)
        out = "{" + body + "}"
    elif s[i] == "\\":
        j = i + 1
        if j < len(s) and s[j].isalpha():
            while j < len(s) and s[j].isalpha():
                j += 1
            out = s[i:j]
            i = j
            k = i
            while k < len(s) and s[k] == " ":
                k += 1
            if k < len(s) and s[k] == "{":
                g, k2 = _read_group(s, k)
                out = out + "{" + g + "}"
                i = k2
        else:
            j = min(j + 1, len(s))
            out = s[i:j]
            i = j
    else:
        out = s[i]
        i += 1
    while i < len(s) and s[i] in "^_":
        c = s[i]
        i += 1
        content, i = _read_script(s, i)
        out += c + ("{" + content + "}" if len(content) != 1 else content)
    if start == i:
        return "", i
    return out.strip(), i


def _match_cmd(s, i, cmd):
    """True when s[i:] starts with *cmd* and is not a prefix of a longer command."""
    if s[i:i + len(cmd)] != cmd:
        return False
    nxt = i + len(cmd)
    if nxt < len(s) and s[nxt].isalpha():
        return False
    return True


def _parse_flat_expr(s):
    r"""Convert a flat LaTeX expression into a token list.

    Token kinds: text frac sqrt delim nary mathbf plain hat bar tilde vec
    dot ddot operatorname func sup sub
    """
    tokens = []
    i = 0
    buf = ""
    while i < len(s):
        c = s[i]

        # \frac{..}{..} / \dfrac / \tfrac
        len_frac = 6 if s[i:i + 6] == "\\dfrac" else (6 if s[i:i + 6] == "\\tfrac" else 0)
        if len_frac and i + len_frac < len(s) and s[i + len_frac] == "{":
            if buf:
                tokens.append(("text", buf)); buf = ""
            i += len_frac
            num, i = _read_group(s, i)
            den = ""
            if i < len(s) and s[i] == "{":
                den, i = _read_group(s, i)
            tokens.append(("frac", num.strip(), den.strip()))
            continue
        if s[i:i + 5] == "\\frac" and i + 5 < len(s) and s[i + 5] == "{":
            if buf:
                tokens.append(("text", buf)); buf = ""
            i += 5
            num, i = _read_group(s, i)
            den = ""
            if i < len(s) and s[i] == "{":
                den, i = _read_group(s, i)
            tokens.append(("frac", num.strip(), den.strip()))
            continue

        # \sqrt[n]{..}
        if s[i:i + 5] == "\\sqrt" and i + 5 < len(s):
            if buf:
                tokens.append(("text", buf)); buf = ""
            i += 5
            deg = ""
            if i < len(s) and s[i] == "[":
                i += 1
                while i < len(s) and s[i] != "]":
                    deg += s[i]; i += 1
                i += 1
            body = ""
            if i < len(s) and s[i] == "{":
                body, i = _read_group(s, i)
            tokens.append(("sqrt", deg.strip(), body.strip()))
            continue

        # n-ary: \sum \prod \int ... with optional limits and one operand
        nary_hit = None
        for cmd in sorted(NARY, key=len, reverse=True):
            if _match_cmd(s, i, cmd):
                nary_hit = cmd
                break
        if nary_hit is not None:
            if buf:
                tokens.append(("text", buf)); buf = ""
            i += len(nary_hit)
            sub = sup = ""
            for _ in range(2):
                j = i
                while j < len(s) and s[j] == " ":
                    j += 1
                if j < len(s) and s[j] in "^_":
                    mark = s[j]
                    content, j = _read_script(s, j + 1)
                    if mark == "^":
                        sup = content
                    else:
                        sub = content
                    i = j
                else:
                    break
            body, i = _read_atom(s, i)
            glyph, limloc = NARY[nary_hit]
            tokens.append(("nary", glyph, limloc, sub, sup, body))
            continue

        # \left<d> ... \right<d>
        if s[i:i + 5] == "\\left" and i + 5 < len(s) and s[i + 5] in _DELIM_BEG:
            if buf:
                tokens.append(("text", buf)); buf = ""
            i += 5
            beg, i = _read_delim_char(s, i)
            depth = 1; j = i; end = -1
            while j < len(s):
                if s[j:j + 5] == "\\left" and j + 5 < len(s) and s[j + 5] in _DELIM_BEG:
                    depth += 1; j += 5
                elif s[j:j + 6] == "\\right" and j + 6 < len(s) and s[j + 6] in _DELIM_END:
                    depth -= 1
                    if depth == 0:
                        end = j; break
                    j += 6
                else:
                    j += 1
            if end < 0:
                tokens.append(("text", "\\left" + beg))
                continue
            inner = s[i:end]
            i = end + 6
            endchr, i = _read_delim_char(s, i)
            tokens.append(("delim", beg, endchr, inner))
            continue

        # \| ... \|  -> norm delimiters
        if s[i:i + 2] == "\\|":
            if buf:
                tokens.append(("text", buf)); buf = ""
            nxt = s.find("\\|", i + 2)
            if nxt >= 0:
                tokens.append(("delim", "\u2016", "\u2016", s[i + 2:nxt]))
                i = nxt + 2
            else:
                tokens.append(("text", "\u2016"))
                i += 2
            continue

        # spacing
        if s[i:i + 6] == "\\qquad":
            if buf:
                tokens.append(("text", buf)); buf = ""
            tokens.append(("text", "\u3000\u3000")); i += 6
            continue
        if s[i:i + 5] == "\\quad":
            if buf:
                tokens.append(("text", buf)); buf = ""
            tokens.append(("text", "\u3000")); i += 5
            continue
        if s[i:i + 2] in ("\\,", "\\;", "\\!"):
            if buf:
                tokens.append(("text", buf)); buf = ""
            tokens.append(("text", " ")); i += 2
            continue

        # group commands
        grp_typ = None
        for cmd, typ in GROUP_CMDS:
            if _match_cmd(s, i, cmd):
                grp_typ = typ
                i += len(cmd)
                break
        if grp_typ is not None:
            if buf:
                tokens.append(("text", buf)); buf = ""
            while i < len(s) and s[i] == " ":
                i += 1
            if i < len(s) and s[i] == "{":
                content, i = _read_group(s, i)
            elif i < len(s) and s[i] == "\\":
                k = i + 1
                while k < len(s) and s[k].isalpha():
                    k += 1
                if k == i + 1:
                    k = min(k + 1, len(s))
                content = s[i:k]; i = k
            elif i < len(s):
                content = s[i]; i += 1
            else:
                content = ""
            tokens.append((grp_typ, content.strip()))
            continue

        # function names
        func_hit = None
        for cmd in FUNC_CMDS:
            if _match_cmd(s, i, cmd):
                func_hit = cmd
                break
        if func_hit is not None:
            if buf:
                tokens.append(("text", buf)); buf = ""
            tokens.append(("func", func_hit[1:]))
            i += len(func_hit)
            continue

        # ^ and _
        if c in "^_" and i + 1 < len(s):
            if buf:
                tokens.append(("text", buf)); buf = ""
            typ = "sup" if c == "^" else "sub"
            i += 1
            content, i = _read_script(s, i)
            tokens.append((typ, content))
            continue

        buf += c
        i += 1
    if buf:
        tokens.append(("text", buf))
    return tokens


def _styled_run(text, plain=False, bold=False):
    """Build one <m:r>; plain forces upright, bold adds w:b."""
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
    for r in elem.iter("{%s}r" % NS):
        if r.find("{%s}rPr" % WNS) is None:
            wrpr = ET.Element("{%s}rPr" % WNS)
            ET.SubElement(wrpr, "{%s}b" % WNS)
            r.insert(0, wrpr)
        mrpr = r.find("{%s}rPr" % NS)
        if mrpr is None:
            mrpr = ET.Element("{%s}rPr" % NS)
            r.insert(1, mrpr)
        if mrpr.find("{%s}sty" % NS) is None:
            sty = ET.SubElement(mrpr, "{%s}sty" % NS)
            sty.set("{%s}val" % NS, "b")


def _plain_runs(elem):
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
    om = el("oMath")
    _append_tokens(om, toks)
    return om


def _acc(om, mark, body):
    acc = el("acc")
    accPr = el("accPr")
    accPr.append(_val_el("chr", mark))
    acc.append(accPr)
    e_el = el("e")
    _append_tokens(e_el, _parse_flat_expr(body))
    acc.append(e_el)
    om.append(acc)


def _append_tokens(om, toks):
    for t in toks:
        typ = t[0]
        if typ == "text":
            om.append(mr(_apply_maps(t[1])))
        elif typ == "func":
            om.append(_styled_run(t[1], plain=True))
        elif typ == "frac":
            f = el("f")
            num = el("num")
            _append_tokens(num, _parse_flat_expr(t[1] if t[1] else ""))
            den = el("den")
            _append_tokens(den, _parse_flat_expr(t[2] if t[2] else ""))
            f.append(num); f.append(den)
            om.append(f)
        elif typ == "sqrt":
            rad = el("rad")
            if t[1]:
                deg = el("deg")
                _append_tokens(deg, _parse_flat_expr(t[1]))
                rad.append(deg)
            e_el = el("e")
            _append_tokens(e_el, _parse_flat_expr(t[2] if t[2] else ""))
            rad.append(e_el)
            om.append(rad)
        elif typ == "delim":
            d = el("d")
            dPr = el("dPr")
            dPr.append(_val_el("begChr", t[1]))
            dPr.append(_val_el("endChr", t[2]))
            d.append(dPr)
            e_el = el("e")
            _append_tokens(e_el, _parse_flat_expr(t[3]))
            d.append(e_el)
            om.append(d)
        elif typ == "nary":
            n = el("nary")
            nPr = el("naryPr")
            nPr.append(_val_el("chr", t[1]))
            nPr.append(_val_el("limLoc", t[2]))
            nPr.append(_val_el("subHide", "0" if t[3] else "1"))
            nPr.append(_val_el("supHide", "0" if t[4] else "1"))
            n.append(nPr)
            sub = el("sub")
            if t[3]:
                _append_tokens(sub, _parse_flat_expr(t[3]))
            sup = el("sup")
            if t[4]:
                _append_tokens(sup, _parse_flat_expr(t[4]))
            e_el = el("e")
            if t[5]:
                _append_tokens(e_el, _parse_flat_expr(t[5]))
            n.append(sub); n.append(sup); n.append(e_el)
            om.append(n)
        elif typ in ("mathbf", "plain", "operatorname"):
            sub = _build(_parse_flat_expr(t[1]))
            if typ == "mathbf":
                _bold_runs(sub)
            else:
                _plain_runs(sub)
            for child in list(sub):
                if typ == "operatorname":
                    pass
                om.append(child)
        elif typ in ("hat", "tilde", "vec", "dot", "ddot"):
            _acc(om, ACCENTS["\\" + typ], t[1])
        elif typ == "bar":
            bar = el("bar")
            barPr = el("barPr")
            barPr.append(_val_el("pos", "top"))
            bar.append(barPr)
            e_el = el("e")
            _append_tokens(e_el, _parse_flat_expr(t[1]))
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
    except Exception as e:  # pragma: no cover - defensive
        r = el("oMath")
        r.append(mr("[ERR:%s]" % str(e)[:40]))
        return ET.tostring(r, encoding="unicode")


def latex_to_omml_para(expr):
    o = latex_to_omml(expr)
    if not o:
        return ""
    return ('<m:oMathPara xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            '%s</m:oMathPara>' % o)


def latex_to_omml_inline(expr):
    return latex_to_omml(expr)


# ----- Markdown equation extraction -----
EQ_DISPLAY = re.compile(r"\$\$\s*(.+?)\s*\$\$", re.DOTALL)
EQ_INLINE = re.compile(r"(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)")
EQ_ANY = re.compile(r"\$\$\s*(.+?)\s*\$\$|(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)", re.DOTALL)


def extract_equations(md):
    """Single-pass split so inline formulas between display blocks survive."""
    segs = []
    pos = 0
    for m in EQ_ANY.finditer(md):
        if m.start() > pos:
            segs.append(("md", md[pos:m.start()]))
        if m.group(1) is not None:
            segs.append(("display", m.group(1).strip()))
        else:
            segs.append(("inline", m.group(2).strip()))
        pos = m.end()
    if pos < len(md):
        segs.append(("md", md[pos:]))
    return segs

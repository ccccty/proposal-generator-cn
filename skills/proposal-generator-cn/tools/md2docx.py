# -*- coding: utf-8 -*-
import re, sys, os
from docx import Document
from docx.shared import Pt, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from latex_omml import latex_to_omml_para, latex_to_omml_inline, extract_equations, EQ_DISPLAY, EQ_INLINE
from docx.oxml import OxmlElement

FONT_BODY='仿宋_GB2312'; FONT_H1='黑体'; FONT_H2='楷体_GB2312'; FONT_H3='仿宋_GB2312'; FONT_TBL='仿宋_GB2312'
BOLD_SEP = re.compile(r"(\*\*[^*]+\*\*)")

def set_run(run, cn, size, bold=False):
    run.font.name = 'Times New Roman'
    run.font.size = Pt(size)
    run.bold = bold
    run._element.rPr.rFonts.set(qn('w:eastAsia'), cn)

def _indent(p, chars):
    if not chars: return
    ind = OxmlElement('w:ind')
    ind.set(qn('w:firstLineChars'), str(int(chars*100)))
    p._p.get_or_add_pPr().append(ind)

def _outline(p, lvl):
    pPr = p._p.get_or_add_pPr()
    o = OxmlElement('w:outlineLvl'); o.set(qn('w:val'), str(lvl)); pPr.append(o)

def para(doc, text, cn=FONT_BODY, size=12, bold=False, align=None, indent_chars=2,
         space_before=0, space_after=0, outline=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    if space_before: pf.space_before = Pt(space_before)
    if space_after: pf.space_after = Pt(space_after)
    if align: pf.alignment = align
    _indent(p, indent_chars)
    if outline is not None: _outline(p, outline)
    for seg in BOLD_SEP.split(text):
        if not seg: continue
        b = bold; s = seg
        if seg.startswith('**') and seg.endswith('**') and len(seg) > 4:
            s = seg[2:-2]; b = True
        set_run(p.add_run(s), cn, size, b)
    return p

def add_toc(doc, levels=3):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'TOC \\o "1-%d" \\h \\z \\u' % levels)
    r = OxmlElement('w:r'); t = OxmlElement('w:t')
    t.text = '（在此处按 F9 或右键“更新域”生成目录）'
    r.append(t); fld.append(r); p._p.append(fld)
    return p

def add_table(doc, rows):
    if not rows: return
    ncol = max(len(r) for r in rows)
    t = doc.add_table(rows=0, cols=ncol)
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, r in enumerate(rows):
        cells = t.add_row().cells
        for j in range(ncol):
            txt = r[j] if j < len(r) else ''
            c = cells[j]; c.text = ''
            p = c.paragraphs[0]
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
            p.paragraph_format.space_before = Pt(1); p.paragraph_format.space_after = Pt(1)
            if i == 0: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for seg in BOLD_SEP.split(txt):
                if not seg: continue
                b = (i == 0); s = seg
                if seg.startswith('**') and seg.endswith('**') and len(seg) > 4:
                    s = seg[2:-2]; b = True
                set_run(p.add_run(s), FONT_TBL, 10.5, b)
    return t

def _insert_omml(p, omml_xml, display=False):
    """Insert OMML XML into a paragraph as an inline or display equation."""
    # OMML must go into a run's alternate content or directly into paragraph
    from lxml import etree
    try:
        omml_el = etree.fromstring(omml_xml.encode('utf-8'))
        # For display: insert as standalone oMathPara in paragraph
        # For inline: wrap in run
        if display:
            p._p.append(omml_el)
        else:
            r = p.add_run()
            r._r.append(omml_el)
    except Exception as e:
        p.add_run('[EQ:' + str(e)[:40] + ']')

def _needs_lxml():
    global LXML_OK
    try:
        from lxml import etree
        LXML_OK = True
        return True
    except ImportError:
        LXML_OK = False
        return False

LXML_OK = False

def parse_table(lines, i):
    rows = []
    while i < len(lines) and lines[i].strip().startswith('|'):
        raw = lines[i].strip().strip('|')
        cells = [c.strip() for c in raw.split('|')]
        sep = True
        for c in cells:
            if c and not re.fullmatch(r':?-{2,}:?', c): sep = False
        if not sep: rows.append(cells)
        i += 1
    return rows, i

def build(md, out, title=None, base_dir=None):
    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = Cm(3.0); sec.right_margin = Cm(3.0)
    sec.top_margin = Cm(2.54); sec.bottom_margin = Cm(2.54)
    st = doc.styles['Normal']; st.font.name='Times New Roman'; st.font.size=Pt(12)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), FONT_BODY)
    if title:
        para(doc, title, FONT_H1, 18, align=WD_ALIGN_PARAGRAPH.CENTER, indent_chars=0,
             space_before=24, space_after=24)
        para(doc, '目  录', FONT_H1, 16, align=WD_ALIGN_PARAGRAPH.CENTER, indent_chars=0,
             space_before=12, space_after=6)
        add_toc(doc)
        doc.add_page_break()
    _needs_lxml()
    segs = extract_equations(md) if LXML_OK else [('md', md)]
    if LXML_OK and segs:
        lines = []
        for typ, content in segs:
            if typ == 'md':
                lines.extend(content.split(chr(10)))
            elif typ == 'display':
                lines.append(chr(60) + chr(60) + 'EQ_DISPLAY:' + content.replace(chr(92), chr(92)+chr(92)) + chr(62) + chr(62))
            elif typ == 'inline':
                lines.append(chr(60) + chr(60) + 'EQ_INLINE:' + content.replace(chr(92), chr(92)+chr(92)) + chr(62) + chr(62))
    else:
        lines = md.split(chr(10))
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s: i += 1; continue
        if s == '<<PAGEBREAK>>':
            doc.add_page_break(); i += 1; continue
        if s.startswith('|'):
            rows, i = parse_table(lines, i); add_table(doc, rows); continue
        m = re.match(r'^(#{1,6})\s+(.*)$', s)
        if m:
            lvl = len(m.group(1)); txt = m.group(2).strip()
            if lvl == 1:
                para(doc, txt, FONT_H1, 16, align=WD_ALIGN_PARAGRAPH.CENTER, indent_chars=0,
                     space_before=12, space_after=8, outline=0)
            elif lvl == 2:
                para(doc, txt, FONT_H1, 16, indent_chars=0, space_before=14, space_after=6, outline=1)
            elif lvl == 3:
                para(doc, txt, FONT_H2, 16, indent_chars=2, space_before=8, space_after=4, outline=2)
            elif lvl == 4:
                para(doc, txt, FONT_H3, 14, bold=True, indent_chars=2, space_before=5, outline=3)
            elif lvl == 5:
                para(doc, txt, FONT_H3, 13, bold=True, indent_chars=2, space_before=3, outline=4)
            elif lvl == 6:
                para(doc, txt, FONT_BODY, 12, bold=True, indent_chars=2)
            else:
                para(doc, txt, FONT_BODY, 12, bold=True, indent_chars=2)
            i += 1; continue
        m_img = re.match(r'^!\[(.+?)\]\((.+?)\)', s)
        if m_img:
            caption, img_rel = m_img.group(1).strip(), m_img.group(2).strip()
            img_path = img_rel if os.path.isabs(img_rel) else os.path.join(base_dir or '.', img_rel)
            if os.path.isfile(img_path):
                p = doc.add_paragraph()
                p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
                p.add_run().add_picture(img_path, width=Inches(5.5))
                para(doc, caption, FONT_H1, 10.5, align=WD_ALIGN_PARAGRAPH.CENTER, indent_chars=0,
                     space_before=2, space_after=6)
            else:
                para(doc, '[图片缺失: ' + img_rel + ']', FONT_BODY, 12, indent_chars=2)
            i += 1; continue
        if re.match(r'^图\s?\d|^表\s?\d', s):
            para(doc, s, FONT_H2, 10.5, align=WD_ALIGN_PARAGRAPH.CENTER, indent_chars=0,
                 space_before=2, space_after=6); i += 1; continue
        if s.startswith(chr(62)):
            para(doc, s.lstrip(chr(62) + ' ').strip(), FONT_H2, 12, indent_chars=2); i += 1; continue
        if s.startswith(chr(60)+chr(60)+'EQ_DISPLAY:') and LXML_OK:
            expr = s[13:-2].replace(chr(92)+chr(92), chr(92))
            p = para(doc, '', FONT_BODY, 12, align=WD_ALIGN_PARAGRAPH.CENTER, indent_chars=0, space_before=2, space_after=2)
            _insert_omml(p, latex_to_omml_para(expr), display=True)
            i += 1; continue
        if s.startswith(chr(60)+chr(60)+'EQ_INLINE:') and LXML_OK:
            expr = s[12:-2].replace(chr(92)+chr(92), chr(92))
            p = para(doc, '', FONT_BODY, 12, indent_chars=2, space_before=0, space_after=0)
            _insert_omml(p, latex_to_omml_inline(expr), display=False)
            i += 1; continue
        para(doc, s, FONT_BODY, 12, indent_chars=2)
        i += 1
    doc.save(out)
    return out

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    md = open(src, encoding='utf-8').read()
    title = None
    m = re.search(r'^#\s+(.+)$', md, re.M)
    if m:
        title = m.group(1).strip()
        md = md[:m.start()] + md[m.end():]
    build(md, dst, title, base_dir=os.path.dirname(os.path.abspath(src)))
    print('saved', dst, os.path.getsize(dst))
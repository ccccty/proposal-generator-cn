# -*- coding: utf-8 -*-
r"""交付前检查 .docx 是否"干净"（纯标准库）。

只查那些肉眼容易漏、但评审一眼就能看见的问题：
  1. 公式里残留字面反斜杠（\tilde、\sum 之类没被转换成功）
  2. 相邻重复题注（同一张图出现两条 "图1-1 ..."）
  3. 图片数量与 "图N-N" 题注数量不匹配
  4. 字体/字号/页边距/行距的实际取值（供与本单位模板比对）

用法
----
    python verify_docx.py 正文.docx
    python verify_docx.py 正文.docx --json

退出码：0 通过 / 1 存在错误 / 2 用法错误
"""
import argparse
import json
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

NS_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
CAPTION = re.compile(r"^\s*(?:图|表)\s?\d")


def read_xml(zf, name):
    with zf.open(name) as fh:
        return ET.fromstring(fh.read())


def para_texts(root):
    out = []
    for p in root.iter(NS_W + "p"):
        txt = "".join(t.text or "" for t in p.iter(NS_W + "t"))
        out.append(txt)
    return out


def cm_from_twips(v):
    try:
        return round(int(v) / 566.929, 2)
    except (TypeError, ValueError):
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="检查 .docx 交付件是否干净")
    ap.add_argument("input", help="待检查的 .docx 文件")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = ap.parse_args(argv)

    try:
        zf = zipfile.ZipFile(args.input)
    except (OSError, zipfile.BadZipFile):
        print("不是有效的 .docx：%s" % args.input, file=sys.stderr)
        return 2

    with zf:
        root = read_xml(zf, "word/document.xml")
        names = zf.namelist()

    errors = []
    warns = []

    math_texts = [t.text or "" for t in root.iter(NS_M + "t")]
    for txt in math_texts:
        if "\\" in txt:
            errors.append({
                "rule": "公式#1 残留字面反斜杠",
                "detail": txt[:60],
            })

    texts = para_texts(root)
    for i in range(1, len(texts)):
        prev, cur = texts[i - 1].strip(), texts[i].strip()
        if prev and prev == cur and CAPTION.match(cur):
            errors.append({
                "rule": "图表#1 题注重复",
                "detail": "%s（段落 %d、%d）" % (cur[:30], i - 1, i),
            })

    images = len(list(root.iter(NS_A + "blip")))
    fig_caps = [t for t in texts if re.match(r"^\s*图\s?\d", t.strip())]
    if fig_caps and images != len(fig_caps):
        warns.append({
            "rule": "图表#2 图片数与图题注数不一致",
            "detail": "图片 %d 张，图题注 %d 条" % (images, len(fig_caps)),
        })

    fonts = {}
    sizes = {}
    for r in root.iter(NS_W + "r"):
        rf = r.find(".//" + NS_W + "rFonts")
        if rf is not None:
            ea = rf.get(NS_W + "eastAsia")
            if ea:
                fonts[ea] = fonts.get(ea, 0) + 1
        sz = r.find(".//" + NS_W + "sz")
        if sz is not None:
            v = sz.get(NS_W + "val")
            if v:
                half = int(v) / 2.0
                sizes[half] = sizes.get(half, 0) + 1

    sect = root.find(".//" + NS_W + "sectPr")
    margins = {}
    if sect is not None:
        pg = sect.find(NS_W + "pgMar")
        if pg is not None:
            margins = {
                "top": cm_from_twips(pg.get(NS_W + "top")),
                "bottom": cm_from_twips(pg.get(NS_W + "bottom")),
                "left": cm_from_twips(pg.get(NS_W + "left")),
                "right": cm_from_twips(pg.get(NS_W + "right")),
            }

    spacing = set()
    for sp in root.iter(NS_W + "spacing"):
        v = sp.get(NS_W + "line")
        if v:
            spacing.add(round(int(v) / 240.0, 2))

    omath = len(list(root.iter(NS_M + "oMath")))
    report = {
        "file": args.input,
        "paragraphs": len(texts),
        "equations": omath,
        "images": images,
        "figure_captions": len(fig_caps),
        "fonts": dict(sorted(fonts.items(), key=lambda kv: -kv[1])),
        "sizes_pt": dict(sorted(sizes.items(), key=lambda kv: -kv[1])),
        "margins_cm": margins,
        "line_spacing": sorted(spacing),
        "errors": errors,
        "warnings": warns,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("检查：%s" % args.input)
        print("段落 %d / 公式 %d / 图片 %d / 图题注 %d" % (
            len(texts), omath, images, len(fig_caps)))
        print("字体：%s" % ("，".join("%s(%d)" % kv for kv in report["fonts"].items()) or "未识别"))
        print("字号：%s" % ("，".join("%spt(%d)" % kv for kv in report["sizes_pt"].items()) or "未识别"))
        print("页边距(cm)：%s" % report["margins_cm"])
        print("行距倍数：%s" % report["line_spacing"])
        for e in errors:
            print("  [错误] %s：%s" % (e["rule"], e["detail"]))
        for w in warns:
            print("  [警告] %s：%s" % (w["rule"], w["detail"]))
        print("结论：%s（错误 %d，警告 %d）" % (
            "不通过" if errors else "通过", len(errors), len(warns)))

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

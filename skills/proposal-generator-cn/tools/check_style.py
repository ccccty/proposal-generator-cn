# -*- coding: utf-8 -*-
"""AI 味体检（纯标准库，无需安装依赖）。

把「去 AI 味」这道语言层工序里**可机械判定**的部分做成检查，配合 humanizer 技能使用：
  1. 破折号（中文破折号 / 短破折号 / 空格连字符）——错误
  2. 否定对照（不是…而是 / 并非…而是 / 不仅…更 / 不只是…更是 / 与其说…不如说）——错误
  3. 装饰符号（emoji、箭头、对勾）——错误
  4. 行首加粗小标签与全文加粗数量——警告
  5. 空泛套话词表（赋能 / 助力 / 抓手 / 深度融合 / 具有重要意义 / 研究表明…）——警告
  6. 公文套话句式（随着…的快速发展 / 在…的大背景下 / 为…提供有力支撑）——警告

只查「怎么写」，不查「写了什么」：数值、公式、图表、经费一律不涉及（那是
check_proposal.py 的职责）。代码块、行内代码、HTML 注释与公式内的文本不检查。

用法
----
    python check_style.py 正文.md
    python check_style.py 正文.md --json
    python check_style.py 正文.md --warn-only

退出码：0 通过（可能有警告）/ 1 存在错误 / 2 用法错误
"""
import argparse
import json
import os
import re
import sys

BT = chr(96)  # 反引号，用于在源码里拼代码块标记

# 破折号：中文破折号、短破折号、以及被当破折号用的空格连字符
DASH = re.compile(r"——|—|–|\s--\s")

CONTRASTS = [
    ("AI味#1 否定对照（不是…而是）", r"不是[^。；\n]{1,40}?而是", "error"),
    ("AI味#1 否定对照（并非…而是）", r"并非[^。；\n]{1,40}?而是", "error"),
    ("AI味#1 否定对照（不仅…更）", r"不仅[^。；\n]{1,40}?更", "error"),
    ("AI味#1 否定对照（不只是…更是）", r"不只是[^。；\n]{1,40}?更是", "error"),
    ("AI味#1 否定对照（与其说…不如说）", r"与其说[^。；\n]{1,40}?不如说", "error"),
    ("AI味#1 递进并列（不仅…而且）", r"不仅[^。；\n]{1,40}?(?:而且|并且)", "warn"),
]

DECORATION = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]|✓|✔|★|☆")
ARROW = re.compile(r"→|⇒|←|⇐")

BOLD_ANY = re.compile(r"\*\*[^*\n]{1,40}\*\*")
BOLD_LABEL = re.compile(r"^\s*(?:[-*+]\s+)?\*\*[^*\n]{1,24}\*\*\s*[：:]")

BUZZWORDS = [
    "赋能", "助力", "抓手", "深度融合", "多维度", "多层次", "全方位",
    "新范式", "生态位", "组合拳", "痛点", "闭环生态", "旨在", "致力于",
    "有效地", "很好地", "较好地", "具有重要意义", "意义重大",
    "值得注意的是", "不难看出", "众所周知", "综上所述",
    "大量实验表明", "研究表明", "实践表明",
    "提供了有力支撑", "奠定坚实基础", "显著提升", "大幅提升",
]

SET_PHRASES = [
    ("套话 随着…的快速发展", r"随着[^。；\n]{0,24}?的(?:不断)?(?:快速|飞速|迅猛)?(?:发展|推进|深入|升级|演进)"),
    ("套话 在…的大背景下", r"在[^。；\n]{0,24}?的(?:大背景|大趋势|新时代)下"),
    ("套话 为…提供支撑/奠定基础", r"为[^。；\n]{0,24}?(?:提供(?:了)?(?:有力|强有力|坚实)?支撑|奠定(?:了)?(?:坚实|良好|扎实)?基础)"),
]

# 不宜机械判定的介词对照：「以 A 而非 B」在技术文本里常带真实信息，只提示
SOFT_CONTRAST = ("AI味#1 对照（…而非…：确认对照对象真实存在）", r"而非")


def read_text(path):
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with open(path, encoding=enc) as fh:
                return fh.read()
        except UnicodeDecodeError:
            continue
    raise SystemExit("无法解码文件：%s" % path)


def mask_noise(text):
    """把代码块、行内代码、HTML 注释、公式整段替换为等长空白，保留换行以维持行号。"""

    def blanks(m):
        s = m.group(0)
        return "".join("\n" if ch == "\n" else " " for ch in s)

    patterns = (
        BT * 3 + r"[\s\S]*?" + BT * 3,
        r"<!--[\s\S]*?-->",
        r"\$\$[\s\S]*?\$\$",
        r"\$[^$\n]+\$",
        BT + r"[^" + BT + r"\n]*" + BT,
    )
    for pat in patterns:
        text = re.sub(pat, blanks, text)
    return text


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def find_all(text, pat, rule, level, detail_fn=None):
    out = []
    for m in re.finditer(pat, text):
        detail = detail_fn(m) if detail_fn else m.group(0)[:40]
        out.append({
            "level": level,
            "rule": rule,
            "line": line_of(text, m.start()),
            "detail": detail,
        })
    return out


def check_dash(text):
    out = []
    for m in DASH.finditer(text):
        tok = m.group(0).strip()
        if tok in ("—", "–"):
            before = text[m.start() - 1:m.start()]
            after = text[m.end():m.end() + 1]
            if before.isdigit() and after.isdigit():
                continue  # 数值区间（2019—2021 之类），不是破折号
        out.append({
            "level": "error",
            "rule": "AI味#2 破折号",
            "line": line_of(text, m.start()),
            "detail": "「%s」→ 改逗号/冒号/括号，或拆句" % tok,
        })
    return out


def check_contrast(text):
    out = []
    for rule, pat, level in CONTRASTS:
        out.extend(find_all(text, pat, rule, level,
                            lambda m: "「%s」→ 直接陈述结论，删掉否定铺垫" % m.group(0)[:40]))
    rule, pat = SOFT_CONTRAST
    out.extend(find_all(text, pat, rule, "warn",
                        lambda m: "确认「而非」前后的对象都真实存在，否则删"))
    return out


def check_decoration(text):
    return find_all(text, DECORATION, "AI味#3 装饰符号", "error",
                    lambda m: "「%s」删；技术流程用图，不用装饰符号" % m.group(0))


def check_arrow(text):
    return find_all(text, ARROW, "AI味#3 箭头字符", "warn",
                    lambda m: "「%s」改成文字连接（输入、处理、输出），或用图表达" % m.group(0))


def check_bold(text):
    out = find_all(text, BOLD_LABEL, "AI味#4 行首加粗小标签", "warn",
                   lambda m: "「%s」→ 去掉加粗与冒号，写成句子" % m.group(0).strip()[:30])
    total = len(BOLD_ANY.findall(text))
    if total:
        out.append({
            "level": "warn",
            "rule": "AI味#4 正文加粗",
            "line": 0,
            "detail": "正文共 %d 处加粗；申报正文不加粗，层级用标题与编号表达" % total,
        })
    return out


def check_vocabulary(text):
    out = []
    for word in BUZZWORDS:
        for m in re.finditer(re.escape(word), text):
            out.append({
                "level": "warn",
                "rule": "AI味#5 空泛词",
                "line": line_of(text, m.start()),
                "detail": "「%s」→ 换成具体动作或具体数值" % word,
            })
    return out


def check_set_phrases(text):
    out = []
    for rule, pat in SET_PHRASES:
        for m in re.finditer(pat, text):
            out.append({
                "level": "warn",
                "rule": rule,
                "line": line_of(text, m.start()),
                "detail": "「%s」→ 直接写需求、能力缺口或具体指标" % m.group(0)[:40],
            })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="申报正文 AI 味体检（破折号/否定对照/套话/加粗）")
    ap.add_argument("input", help="待检查的 .md 文件")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--warn-only", action="store_true", help="警告也视为失败")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.input):
        print("文件不存在：%s" % args.input, file=sys.stderr)
        return 2
    raw = read_text(args.input)
    text = mask_noise(raw)

    findings = []
    for fn in (check_dash, check_contrast, check_decoration, check_arrow,
               check_bold, check_vocabulary, check_set_phrases):
        findings.extend(fn(text))

    # 文体示范文件里刻意含反例与结构箭头：只提示，不判失败（与 check_proposal.py 同口径）
    is_demo = "本文件是文体示范" in raw
    if is_demo:
        for f in findings:
            f["level"] = "warn"
    findings.sort(key=lambda f: (0 if f["level"] == "error" else 1, f["line"]))

    errors = [f for f in findings if f["level"] == "error"]
    warns = [f for f in findings if f["level"] == "warn"]

    if args.json:
        print(json.dumps({
            "file": os.path.abspath(args.input),
            "errors": len(errors),
            "warnings": len(warns),
            "findings": findings,
        }, ensure_ascii=False, indent=2))
    else:
        print("AI 味体检：%s" % os.path.abspath(args.input))
        if is_demo:
            print("（识别为文体示范文件：反例与结构箭头只提示，不判失败）")
        print("字数（去空白）：%d" % len(re.sub(r"\s", "", raw)))
        if not findings:
            print("结果：无问题")
        for f in findings:
            loc = ("L%d" % f["line"]) if f["line"] else "-"
            print("  [%s] %s %s：%s" % ("错误" if f["level"] == "error" else "警告",
                                        loc, f["rule"], f["detail"]))
        print("汇总：错误 %d 条，警告 %d 条" % (len(errors), len(warns)))

    if errors:
        return 1
    if args.warn_only and warns:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

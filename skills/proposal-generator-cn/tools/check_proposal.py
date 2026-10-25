# -*- coding: utf-8 -*-
"""申报正文自检脚本（纯标准库，无需安装依赖）。

把 SKILL.md 里"靠人眼逐条核对"的规则变成可执行检查：
  1. 文体铁律 11 条禁令（错误）
  2. 指标五拍法：有数值无基线（警告）
  3. 图表编号连续性与图题注配对（错误/警告）
  4. 经费勾稽：分项之和 vs 总经费、管理费占比（警告）
  5. 篇幅配比：研究内容是否占总正文 60-70% 区间（警告）
  6. 结构要素缺失（警告）
  7. 对冲词密度（警告）

用法
----
    python check_proposal.py 正文.md
    python check_proposal.py 正文.md --json
    python check_proposal.py 正文.md --warn-only

退出码：0 通过（可能有警告）/ 1 存在错误 / 2 用法错误
"""
import argparse
import json
import os
import re
import sys

FORBIDDEN = [
    ("文体#1 待核实标记", r"(【\s*待(?:核实|确认|定)\s*】|\[待(?:核实|确认|定)\]|\bTBD\b|待核实|待确认|待定稿)"),
    ("文体#2 来源标注", r"(来源\s*[:：]|资料来源|据[^\n，。]{0,8}(?:报道|披露)|引自《)"),
    ("文体#3 参考文献/URL", r"(https?://|www\.|参考文献|\[\d+\]\s|doi\s*[:：])"),
    ("文体#4 未取证表述", r"(公开渠道(?:未见|未获取)|未(?:能)?获取|暂缺|未能取证|查询不到)"),
    ("文体#5 草稿声明", r"(草稿|初稿|讨论稿|征求意见稿|供内部讨论)"),
    ("文体#6 合规声明混入正文", r"(非密声明|保密声明|合规声明|涉密审查)"),
    ("文体#7 自查表混入正文", r"(形式审查自查表|打分自评|自查表|打钩清单|逐条打钩)"),
    ("文体#8 AI 使用说明混入正文", r"(本文由\s*AI|使用\s*AI\s*工具撰写|人工智能生成声明)"),
    ("文体#9 写作指令残留", r"(此处插入|待补图|请补充|【图】|（此处）|\{图\d)"),
    ("文体#10 元话语", r"(本文档|本申报书旨在|如上所述，本文件|本文件旨在)"),
]

HEDGE = ["可能", "或许", "大概", "大约", "有待论证", "有待核实", "尚需", "尚待"]
VAGUE = ["显著提升", "大幅提升", "国内领先", "国际领先", "填补空白", "国际先进", "国内先进"]

BASELINE_HINT = re.compile(r"(基线|现有技术|现有方法|目前(?:技术|水平|公开)|当前(?:技术|水平)|主流(?:方法|水平)|典型(?:值|水平)|已达|目前可达)")
INDICATOR_UNIT = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|dB|dBm|km|m/s|m|cm|mm|ms|μs|us|ns|s|min|h|Hz|kHz|MHz|GHz|倍|米|公里|分钟|小时|帧/秒|fps|K|℃)")
INDICATOR_LINE = re.compile(r"(^|[。；\n])\s*(?:指标|性能|精度|分辨|距离|速度|概率|虚警|时延|延迟|重量|功耗|温度|覆盖|识别率|准确率|召回率|吞吐)")

SECTION_KEYS = {
    "立项依据": ["立项依据", "必要性", "研究背景"],
    "研究目标": ["研究目标"],
    "研究内容": ["研究内容"],
    "技术途径": ["技术途径", "技术方案", "技术路线"],
    "创新点": ["创新", "特色"],
    "指标": ["指标", "考核"],
    "经费": ["经费", "概算", "预算"],
    "进度": ["进度", "周期", "里程碑", "阶段"],
    "基础": ["研究基础", "团队", "条件", "保障"],
}


def read_text(path):
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with open(path, encoding=enc) as fh:
                return fh.read()
        except UnicodeDecodeError:
            continue
    raise SystemExit("无法解码文件：%s" % path)


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def check_forbidden(text):
    findings = []
    for label, pat in FORBIDDEN:
        for m in re.finditer(pat, text):
            findings.append({
                "level": "error",
                "rule": label,
                "line": line_of(text, m.start()),
                "detail": m.group(0)[:40],
            })
    return findings


def check_baseline(text):
    findings = []
    lines = text.split("\n")
    skip_section = False
    for idx, line in enumerate(lines):
        if re.match(r"^#{1,4}\s+", line):
            skip_section = bool(re.search(r"反例|禁止这样写|错误示例|反面", line))
        if skip_section:
            continue
        if not (INDICATOR_LINE.search(line) or ("指标" in line and "|" in line)):
            continue
        if not INDICATOR_UNIT.search(line):
            continue
        window = "\n".join(lines[max(0, idx - 3): idx + 4])
        if not BASELINE_HINT.search(window):
            findings.append({
                "level": "warn",
                "rule": "五拍#2 指标缺少基线数值",
                "line": idx + 1,
                "detail": line.strip()[:60],
            })
        if not re.search(r"\d", window.split(line)[0] if line in window else window):
            pass
    for word in VAGUE:
        for m in re.finditer(word, text):
            findings.append({
                "level": "error",
                "rule": "五拍#1 空洞表述",
                "line": line_of(text, m.start()),
                "detail": "%s（须改为带基线的数值表述）" % word,
            })
    return findings


def check_figures(text):
    findings = []
    lines = text.split("\n")
    fig_caps = []
    for idx, line in enumerate(lines):
        m = re.match(r"^\s*图\s?(\d+)\s?[-–—]\s?(\d+)\s*(.*)$", line)
        if not m:
            continue
        fig_caps.append((idx, int(m.group(1)), int(m.group(2)), line.strip()[:40]))
        has_img = any(re.match(r"^\s*!\[", lines[k]) for k in range(max(0, idx - 8), idx + 1))
        if not has_img:
            findings.append({
                "level": "error",
                "rule": "图表#1 题注无对应图片",
                "line": idx + 1,
                "detail": line.strip()[:40],
            })
    seen = {}
    for idx, chap, num, label in fig_caps:
        key = (chap, num)
        if key in seen:
            findings.append({
                "level": "error",
                "rule": "图表#2 图号重复",
                "line": idx + 1,
                "detail": label,
            })
        seen[key] = idx + 1
    by_chap = {}
    for idx, chap, num, label in fig_caps:
        by_chap.setdefault(chap, []).append((num, idx + 1))
    for chap, items in by_chap.items():
        nums = [n for n, _ in items]
        if nums != list(range(1, len(nums) + 1)):
            findings.append({
                "level": "warn",
                "rule": "图表#3 图号不连续",
                "line": items[0][1],
                "detail": "第 %d 章图号序列：%s" % (chap, nums),
            })
    table_nums = [int(m.group(1)) for m in re.finditer(r"^\s*表\s?(\d+)", text, re.M)]
    if table_nums and table_nums != list(range(1, len(table_nums) + 1)):
        findings.append({
            "level": "warn",
            "rule": "图表#4 表号不连续",
            "line": 0,
            "detail": "表号序列：%s" % table_nums,
        })
    return findings


def parse_budget(text):
    """从 markdown 表格里找经费分项，返回 (分项合计, 管理费, 正文总经费)。"""
    total_rows = 0.0
    admin = 0.0
    found_table = False
    for line in text.split("\n"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        label = cells[0]
        if not re.search(r"费|经费|材料|设备|测试|差旅|会议|劳务|专家|管理|间接|直接|外协|燃料|出版|其他", label):
            continue
        nums = []
        for c in cells[1:]:
            m = re.fullmatch(r"\s*([\d,]+(?:\.\d+)?)\s*", c)
            if m:
                nums.append(float(m.group(1).replace(",", "")))
        if not nums:
            continue
        found_table = True
        total_rows += nums[0]
        if "管理费" in label or "间接费用" in label:
            admin += nums[0]
    stated = None
    m = re.search(r"(?:申请|总)?经费\s*(?:为|合计|共)?\s*([\d,]+(?:\.\d+)?)\s*万元", text)
    if m:
        stated = float(m.group(1).replace(",", ""))
    if not found_table:
        return None
    return {"sum": round(total_rows, 2), "admin": round(admin, 2), "stated": stated}


def check_budget(text):
    findings = []
    budget = parse_budget(text)
    if not budget:
        return findings
    if budget["stated"] and abs(budget["sum"] - budget["stated"]) > 0.5:
        findings.append({
            "level": "warn",
            "rule": "经费#1 分项之和与总经费不符",
            "line": 0,
            "detail": "分项合计 %.2f 万元 vs 正文写明 %.2f 万元" % (budget["sum"], budget["stated"]),
        })
    if budget["stated"] and budget["admin"] and budget["admin"] > budget["stated"] * 0.08:
        findings.append({
            "level": "warn",
            "rule": "经费#2 管理费超过 8%",
            "line": 0,
            "detail": "管理费 %.2f / 总经费 %.2f = %.1f%%" % (
                budget["admin"], budget["stated"], budget["admin"] / budget["stated"] * 100),
        })
    return findings


def section_stats(text):
    lines = text.split("\n")
    blocks = []
    cur_title = None
    cur_chars = 0
    for line in lines:
        if re.match(r"^#{1,3}\s+", line):
            if cur_title is not None:
                blocks.append((cur_title, cur_chars))
            cur_title = line
            cur_chars = 0
        else:
            cur_chars += len(re.sub(r"\s", "", line))
    if cur_title is not None:
        blocks.append((cur_title, cur_chars))
    return blocks


def check_ratio(text):
    findings = []
    blocks = section_stats(text)
    total = sum(c for _, c in blocks) or 1
    research = sum(c for t, c in blocks if re.search(r"研究内容", t))
    if not research:
        return findings
    ratio = research / total
    if ratio < 0.50 or ratio > 0.80:
        findings.append({
            "level": "warn",
            "rule": "篇幅#1 研究内容占比偏离",
            "line": 0,
            "detail": "研究内容约 %d 字，占正文 %.1f%%（目标 60-70%%）" % (research, ratio * 100),
        })
    return findings


def check_structure(text):
    findings = []
    heads = "\n".join(re.findall(r"^#{1,4}\s+.*$", text, re.M))
    for section, keys in SECTION_KEYS.items():
        if section in ("指标", "基础"):
            continue
        if not any(k in heads for k in keys):
            findings.append({
                "level": "warn",
                "rule": "结构#1 缺少章节",
                "line": 0,
                "detail": "未找到「%s」相关标题" % section,
            })
    return findings


def check_hedge(text):
    findings = []
    chars = len(re.sub(r"\s", "", text)) or 1
    for word in HEDGE:
        n = text.count(word)
        if n and n / chars * 1000 > 2:
            findings.append({
                "level": "warn",
                "rule": "语气#1 对冲词过密",
                "line": 0,
                "detail": "「%s」出现 %d 次（每千字 %.1f 次）" % (word, n, n / chars * 1000),
            })
    return findings


def check_formula_layout(text):
    """符号说明被写成独立公式行（一个符号一段、一句解释一段）。"""
    findings = []
    lines = text.split("\n")
    # 独立行公式里出现"关系符/运算结构"才说明它是个式子；没有的视为单个符号被孤立。
    OP_TOKENS = ("=", "<", ">", "\\leq", "\\geq", "\\le", "\\ge", "\\approx",
                 "\\to", "\\rightarrow", "\\Rightarrow", "\\pm", "\\mp", "^",
                 "\\frac", "\\dfrac", "\\sqrt", "\\sum", "\\int", "\\prod",
                 "\\lim", "\\log", "\\exp", "\\left", "\\begin", "\\cdot", "\\times")
    for idx, line in enumerate(lines):
        s = line.strip()
        # 1) 孤立的"其中"：下一非空行就是独立公式
        if re.fullmatch(r"其中\s*[:：]?", s):
            nxt = ""
            for k in range(idx + 1, min(idx + 4, len(lines))):
                if lines[k].strip():
                    nxt = lines[k].strip()
                    break
            if nxt.startswith("$$"):
                findings.append({
                    "level": "error",
                    "rule": "公式#1 符号说明被排成竖列",
                    "line": idx + 1,
                    "detail": "「其中」独占一段，紧随单个符号公式；应连写成一句，符号用 $...$ 行内",
                })
            continue
        # 2) 孤立成行的顿号/逗号（并列符号被拆行的残留）
        if re.fullmatch(r"[、，,]\s*", s):
            findings.append({
                "level": "error",
                "rule": "公式#1 符号说明被排成竖列",
                "line": idx + 1,
                "detail": "出现只含标点的段落，说明并列符号被逐行拆开",
            })
            continue
        # 3) 单符号独立公式：$$ 包裹且内部没有任何关系符/运算结构
        m = re.fullmatch(r"\$\$(.{1,40}?)\$\$", s)
        if m and not any(t in m.group(1) for t in OP_TOKENS):
            findings.append({
                "level": "warn",
                "rule": "公式#1 单符号独立成行",
                "line": idx + 1,
                "detail": "%s；若只是解释符号，应写进「其中 $…$ 为 …」的句子里" % s[:40],
            })
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description="申报正文自检（文体/指标/图表/经费/篇幅）")
    ap.add_argument("input", help="待检查的 .md 文件")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--warn-only", action="store_true", help="警告也视为失败")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.input):
        print("文件不存在：%s" % args.input, file=sys.stderr)
        return 2
    text = read_text(args.input)
    is_demo = "本文件是文体示范" in text
    findings = []
    if is_demo:
        # 文体样板里刻意包含"反例"和被批评的写法，不做禁令/基线检查
        checks = [check_figures]
    else:
        checks = [check_forbidden, check_baseline, check_figures,
                  check_budget, check_ratio, check_structure, check_hedge,
                  check_formula_layout]
    for fn in checks:
        findings.extend(fn(text))

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
        print("自检：%s" % os.path.abspath(args.input))
        if is_demo:
            print("（识别为文体样板：只做图表检查，不判禁令/基线）")
        print("字数（去空白）：%d" % len(re.sub(r"\s", "", text)))
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
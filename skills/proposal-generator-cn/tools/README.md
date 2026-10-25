# tools · 工具说明（路径全部按当前目录相对解析，不写死盘符）

| 脚本 | 作用 | 依赖 | 退出码 |
|---|---|---|---|
| `check_proposal.py` | 正文自检：11 条文体禁令、指标基线（五拍）、图表编号、经费勾稽、篇幅配比、章节完整性、对冲词密度 | 纯标准库 | 0 通过 / 1 有错误 / 2 用法错误 |
| `md2docx.py` | Markdown → Word；公式转 Word 原生 OMML；图表题注；目录域；版面可配置 | `python-docx`、`lxml` | 0 / 1（`--strict` 有告警）/ 2 |
| `verify_docx.py` | 交付件复查：公式残留反斜杠、题注重复、图片与题注数量、字体/字号/边距/行距实值 | 纯标准库（读 docx 包内 XML） | 0 / 1 / 2 |
| `latex_omml.py` | 公式引擎（被 md2docx 调用，通常不直接跑） | 纯标准库 | - |
| `format.default.json` | 默认排版配置样板，复制后改 | - | - |

## 找到 Python（不要写死路径）

1. `python` / `python3` / `py -3` 任一可用即可；
2. 系统无 Python 时，用 DSH 的 `load_workspace_dependencies()` 返回的 python 路径（运行时事实）；
3. 都没有：只有 `check_proposal.py` 可用，Word 转换与复查如实报告"未执行"。

缺依赖：`<PY> -m pip install python-docx lxml`

## 典型流程

    <PY> check_proposal.py 正文.md
    <PY> md2docx.py 正文.md 正文.docx --strict
    <PY> verify_docx.py 正文.docx

调整排版（不改代码）：

    <PY> md2docx.py --print-default-config > format.json
    # 改 format.json 里的 fonts / sizes / margins_cm / line_spacing
    <PY> md2docx.py 正文.md 正文.docx --config format.json --strict

## 公式命令边界（实测）

- 可用：`\frac \dfrac \sqrt[n]{} \left...\right \|...\| \sum \prod \int \iint \oint \mathbf \boldsymbol \mathrm \text \operatorname \hat \bar \tilde \vec \dot \ddot`、希腊字母、常用运算符/箭头、`\quad \qquad`。
- 不可用：`\begin{cases}` 等环境、矩阵、`\substack \overset \underset \stackrel`、`\color`、自定义宏。
- **不可用的命令不会报错，而是原样留在公式里**；因此必须 `--strict` + `verify_docx.py` 双保险。
- 完整清单：`../references/10-公式与转换器规范.md`。

## 自测（改完工具后跑一遍）

    <PY> md2docx.py --print-default-config
    <PY> check_proposal.py ../templates/骨架A-项目建议书.md

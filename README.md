# 项目书生成（proposal-generator-cn）

> **一键安装**：已在 [DSH Market](https://dsh.market/) 收录（搜索「proposal-generator-cn」或「项目书」），市场面板里点安装即可。也可手动：`npx @deepseek-ai/dsh plugin --profile desktop add ccccty/proposal-generator-cn`

DSH（DeepSeek Harness）插件：把「项目申报书」写作技能装进你的 DSH。

## 它是什么

一个技能 bundle。安装后，你的 DSH 会话就能按**真实申报件的文体**写项目书：

- **文体铁律**——正文零元信息（11 类禁止项）、指标五拍论证（数值 → 基线 → 为何不够 → 为何能超 → 因此定为该值）、研究内容占正文 60–70%、研究现状按技术演进链写
- **公式规范**——`$$...$$` 与 `$...$` 转 Word 原生 OMML；命令白名单按实测维护，不支持的写法会被工具**叫停**而不是静默留在正文里
- **10 份参考材料**——评分权重、骨架 A/B、写作要点、合规避坑、信源链接、真实申报件拆解、公式与转换器规范（约 600 KB）
- **6 份可复制模板**——骨架 A/B、指标表、经费概算附件、随附清单、自检报告
- **2 份文体样板**——五拍指标论证、研究现状演进链
- **3 件套工具**——正文自检、Markdown→Word、成品 docx 复查

## 安装

### 本地安装（已下载本目录）

    dsh plugin --profile desktop add <本目录路径>

（把 desktop 换成你实际用的 profile；web 版就是 `--profile web`）

### 从 GitHub 安装

    dsh plugin --profile desktop add github:ccccty/proposal-generator-cn

## 使用

新开会话后直接说：

> 用 proposal-generator-cn 技能，根据这份指南写一份项目申报书

或把指南文件丢给会话，技能会自动匹配触发。

## 工具用法（路径按当前技能目录相对解析，不写死盘符）

先找到可用的 Python（`python` / `python3` / `py -3`；都没有时用 DSH 运行时给出的解释器），然后：

    <PY> tools/check_proposal.py 正文.md          # 文体/指标/图表/经费/篇幅自检（零依赖）
    <PY> tools/md2docx.py 正文.md 正文.docx --strict
    <PY> tools/verify_docx.py 正文.docx           # 复查成品：残留反斜杠、重复题注、字体边距

调整排版（不改代码）：

    <PY> tools/md2docx.py --print-default-config > format.json
    <PY> tools/md2docx.py 正文.md 正文.docx --config format.json --strict

依赖：`md2docx.py` 需要 Python 3.8+ 与 `python-docx`、`lxml`；另外两个脚本零依赖。
默认排版（宋体小四 / 黑体四号 / 页边距 2.5、2.8 cm / 1.5 倍行距）只是起点，**以本单位当年度模板为准**。

## drawio（技术路线图导出）

不写死路径：依次看环境变量 `DRAWIO_BIN` → PATH 里的 `drawio` → 常见安装目录；都找不到就问用户要路径，或交付 `.drawio` 源文件由用户自行导出。

## 技能名说明

技能名必须是 kebab-case（`^[a-z0-9-]+$`），所以目录名是 `proposal-generator-cn` 而不是中文「项目书生成」。中文显示名在 description 里。

## 发布到 dsh.so 市场

1. 把本目录推到 GitHub 仓库（名字建议就叫 `proposal-generator-cn`）
2. 在仓库加主题标签 `dsh-plugin`
3. 市场索引会自动抓取，或向 dsh-market 的源列表提交你的仓库

## 目录结构

    skills/proposal-generator-cn/
    ├── SKILL.md              写作规则（12 节）
    ├── references/           00–06、09、10 + 索引（07/08 空缺原因见 references/README.md）
    ├── templates/            6 份可复制模板
    ├── examples/             2 份文体样板
    └── tools/                自检 / 转换 / 复查 / 公式引擎 / 默认排版配置

## 版本

v1.3.0（2026-10-25）· 详见 [CHANGELOG.md](CHANGELOG.md)

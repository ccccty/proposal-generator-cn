# 项目书生成（proposal-generator-cn）

DSH（DeepSeek Harness）插件：把「项目申报书」写作技能装进你的 DSH。

## 它是什么

一个技能 bundle。安装后，你的 DSH 会话就能按**真实申报件的文体**写项目书：

- **§1 文体铁律**——正文零元信息（11 类禁止项）、指标五拍论证（数值→基线→为何不够→为何能超→因此定为该值）、研究内容占正文 60–70%
- **§1.6 公式规范**——LaTeX 数学标记（`$$...$$` 与 `$...$`）白名单，转出的 .docx 里是 Word 原生 OMML 公式
- **9 份素材库**——评分权重、骨架 A/B、写作要点、合规避坑、信源链接、真实申报件拆解（共 ~600 KB）
- **2 个工具**——`md2docx.py`（Markdown→Word，仿宋_GB2312/黑体/楷体排版 + 自动目录 + 公式）与 `latex_omml.py`（LaTeX→OMML 引擎）

## 安装

### 本地安装（已下载本目录）

```powershell
dsh plugin --profile desktop add "D:/work/deepseekherness/对话区2/proposal-generator-cn"
```

（把 desktop 换成你实际用的 profile；web 版就是 `--profile web`）

### 从 GitHub 安装（发布后）

```powershell
dsh plugin --profile desktop add github:<你的用户名>/proposal-generator-cn
```

## 使用

新开会话后直接说：

> 用 proposal-generator-cn 技能，根据这份指南写一份项目申报书

或把指南文件丢给会话，技能会自动匹配触发。

## 工具用法

```powershell
python "C:/Users/<你>/.dsh/profiles/<profile>/node_modules/proposal-generator-cn/skills/proposal-generator-cn/tools/md2docx.py" 输入.md 输出.docx
```

要求：Python 3.8+，`python-docx`、`lxml`。

## 技能名说明

技能名必须是 kebab-case（`^[a-z0-9-]+$`），所以目录名是 `proposal-generator-cn` 而不是中文「项目书生成」。中文显示名在 description 里。

## 发布到 dsh.so 市场

1. 把本目录推到 GitHub 仓库（名字建议就叫 `proposal-generator-cn`）
2. 在仓库加主题标签 `dsh-plugin`
3. 市场索引会自动抓取（awesome 列表机制），或向 dsh-market 的源列表提交你的仓库

## 版本

v1.0.0 · 基于 SKILL.md v1.2（含 §1.6 公式规范）

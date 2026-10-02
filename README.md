<h1 align="center">SISU-IOL-Skill</h1>

面向 **SISU 语言科学研究院** 同学的**课程论文评价与写作辅助 Skill**。它基于参与过该课程的学长学姐的真实论文、对应成绩、作业要求和教师批阅，将其蒸馏为可供 agent 使用的规则，帮助同学判断：**这份论文作业最值得改哪里、为什么、怎样改。**

本skill的流程如下：**先匹配课程、学年与作业**，再结合**对应教师代号的偏好**；没有这门课或该批次的数据时，使用全课程汇总的 **general 分析**。

> [!NOTE]
> **注意：使用项目并不能保证你的实际课程成绩。**

---

## 开始使用

完整复制 `skills/course-grade-guide` 文件夹到支持 `SKILL.md` 的 agent 的技能目录，保留其中的 `courses`、`teachers`、`general` 和 `scripts`。也可以把该目录交给 agent，要求先读取 `SKILL.md`；日常阅读与评价不需要运行 Python。

**示例请求：**

> 使用 course-grade-guide，评价我在 2025-2026 学年第二学期“心理语言学研究方法”的第二次课堂实验报告。请优先指出影响评价的具体问题，定位段落并给出改法。以下是本次要求和草稿……

从 [课程索引](skills/course-grade-guide/courses/index.md) 查看对应关系。教师使用稳定代号，同一代号跨年保持不变；同名课程换教师时创建新开课批次。未知年份不自动选择最近年份。

**未收录课程也可以直接使用：**

> 使用 course-grade-guide。目录里没有我的课程，请先明确说明缺少本课数据，再用 general 分析检查这篇论文的论证和结构，定位最值得修改的段落。以下是本次要求和草稿……

## 项目结构

```text
skills/course-grade-guide/
├─ SKILL.md       使用入口与评价流程
├─ courses/       课程、开课批次与具体作业规则
├─ teachers/      稳定代号与有适用边界的候选偏好
├─ general/       全课程汇总的方法，供无课程数据时使用
└─ scripts/       可选的课程匹配工具
maintainer/       完整案例贡献模板、蒸馏流程及检查工具
```

> [!IMPORTANT]
> 日常只需安装 `skills/course-grade-guide`。
>
> **本仓库保留的是蒸馏后抽象规则**，不上传**任何同学的论文原件或成绩**。

## 当前覆盖与局限

- 已整理 **12 门课程**、**7 个教师代号**、**60 条课程诊断规则**与 **8 项 general 分析方法**。
- 已有材料以仅包含**1位贡献者**的**12门课程评分**。

<details>
<summary><strong>本地工具</strong></summary>

Python 3.10 或以上。课程匹配、校验和测试仅使用标准库；只有 PDF 提取需要 `pypdf`，依赖见 [requirements.txt](maintainer/requirements.txt)。脚本不联网、不调用模型、不自动发布。

在本仓库根目录运行：

```powershell
python -X utf8 skills/course-grade-guide/scripts/resolve_course.py --course 心理语言学研究方法 --year 2025-2026 --assignment report-2
python -X utf8 maintainer/validate.py
python -X utf8 -m unittest discover -s maintainer/tests -v
```

</details>

---

## 如何贡献自己的论文？

贡献须包含实际获评分的论文原件、对应得分及其范围、教师身份、课程、学年与作业类型；有要求、批阅和分项得分时一并提供。

使用 [贡献模板](maintainer/contribution-template.json) 提交文件夹或压缩包。**不要把原件、成绩截图、教师原文批阅或身份映射上传到公开 Issue、讨论或 Pull Request。** 

维护流程见 [蒸馏与更新](maintainer/workflow.md)。公开修改可以提交规则和文档差异，来源核验记录留在私人资料中。

<p align="center">
<strong>我们期待语言科学研究院的你为本项目做出自己的贡献！不论分数高低，都会极大提升skill的准确度和泛用性！</strong>
</p>

import io

p = r"E:\项目\科研小助手\docs\make_intro_pdf.py"
s = io.open(p, encoding="utf-8").read()

pairs = [
    ("交付包剔除演示视频、作品介绍与可再生缓存，",
     "交付包剔除演示视频与全部成品文档（作品介绍、技术文档），只保留源码、库数据与论文原件，"),
    ("解压后为 77 个文件、79.0 MB", "解压后为 74 个文件、78.1 MB"),
    ("剔除演示视频、作品介绍与可再生数据，压至 79.0 MB", "剔除演示视频与成品文档，压至 78.1 MB"),
    ("解压清点 77 个文件", "解压清点 74 个文件"),
    ("keyan-agent-code-1.0.zip（77 文件，79.0 MB）", "keyan-agent-code-1.0.zip（74 文件，78.1 MB）"),
    ("仓库与源码包均不含演示视频与作品介绍 Word 源文件。",
     "仓库与源码包均不含演示视频，也不含作品介绍与技术文档成品，后者按表单第 6 项与需求 3.3 单独提交。"),
]

for a, b in pairs:
    if a not in s:
        print("MISS:", a[:30])
    s = s.replace(a, b)

io.open(p, "w", encoding="utf-8").write(s)
print("patched")

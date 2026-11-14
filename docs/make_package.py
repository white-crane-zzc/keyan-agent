"""打包可提交的作品文件（排除虚拟环境、测试画像、临时目录与明文密钥）。"""
import os
import zipfile
from pathlib import Path

ROOT = Path(r"E:\项目\科研小助手")
DIST = ROOT / "dist"
OUT = DIST / "keyan-agent-code-1.0.zip"

# 顶层目录：整体纳入（app / static / tests 全部文件）
INCLUDE_DIRS = ["app", "static", "tests", "docs"]
# 顶层文件
INCLUDE_FILES = ["README.md", "requirements.txt", "启动.cmd", "run.ps1", ".env.example", ".gitignore"]
# data 下只保留数据库与 PDF 原文
DATA_KEEP = ["library.db", "pdf"]

EXCLUDE_NAMES = {".env", "__pycache__", ".pytest_cache", ".DS_Store", "科研小助手Agent-作品介绍.docx", "演示视频.mp4"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".log"}


def add(zf, path: Path, arc: str):
    zf.write(path, arc)


def main():
    DIST.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    count = 0
    skipped = []
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for name in INCLUDE_DIRS:
            base = ROOT / name
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d not in EXCLUDE_NAMES]
                for fn in filenames:
                    src = Path(dirpath) / fn
                    if fn in EXCLUDE_NAMES or Path(fn).suffix.lower() in EXCLUDE_SUFFIX:
                        skipped.append(str(src))
                        continue
                    arc = str(src.relative_to(ROOT)).replace("\\", "/")
                    add(zf, src, arc)
                    count += 1
        for name in INCLUDE_FILES:
            src = ROOT / name
            if src.exists():
                add(zf, src, name)
                count += 1
        for name in DATA_KEEP:
            base = ROOT / "data" / name
            if base.is_file():
                add(zf, base, f"data/{name}")
                count += 1
            elif base.is_dir():
                for dirpath, dirnames, filenames in os.walk(base):
                    dirnames[:] = [d for d in dirnames if d not in EXCLUDE_NAMES]
                    for fn in filenames:
                        src = Path(dirpath) / fn
                        if fn in EXCLUDE_NAMES:
                            continue
                        arc = str(src.relative_to(ROOT)).replace("\\", "/")
                        add(zf, src, arc)
                        count += 1
    size = OUT.stat().st_size
    print(f"files={count} zip={size/1024/1024:.1f}MB path={OUT}")
    if skipped:
        print("skipped:", len(skipped), skipped[:3])


if __name__ == "__main__":
    main()

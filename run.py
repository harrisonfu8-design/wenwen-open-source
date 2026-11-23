# -*- coding: utf-8 -*-
"""PyInstaller 打包入口。设置环境变量 FK_DOCTOR=1 可写一份依赖自检报告。"""

import os
import sys


def _doctor() -> None:
    """打包后自检：确认 OCR / PDF 渲染等可选能力是否真的可用。"""
    out = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                       "FileKeeper", "doctor.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    lines = [f"python={sys.version.split()[0]} frozen={getattr(sys, 'frozen', False)}"]
    for mod in ("pymupdf", "winrt.windows.media.ocr", "winocr", "PIL", "openpyxl", "docx", "pypdf"):
        try:
            __import__(mod)
            lines.append(f"{mod}: OK")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"{mod}: FAIL {type(exc).__name__} {exc}")
    try:
        from filekeeper import ocr as _ocr
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (900, 160), "white")
        f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 36)
        ImageDraw.Draw(img).text((30, 40), "发票号码：26112000000012345678", font=f, fill="black")
        t = _ocr._run_ocr(img)
        lines.append("ocr: " + (t.replace("\n", " ")[:80] if t else "EMPTY"))
    except Exception as exc:  # noqa: BLE001
        lines.append(f"ocr: FAIL {type(exc).__name__} {exc}")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    sys.exit(0)


if __name__ == "__main__":
    if os.environ.get("FK_DOCTOR"):
        _doctor()
    from filekeeper.main import main
    main()

# -*- coding: utf-8 -*-
"""文文入口。"""

from __future__ import annotations

import os
import sys
import tkinter as tk
import traceback
from tkinter import messagebox

from . import core
from .ui import FileKeeperApp


def _resource(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, rel)


def _install_error_hook(root: tk.Tk) -> None:
    log_path = os.path.join(core.APP_DIR, "error.log")

    def _write(text: str) -> None:
        try:
            core.ensure_app_dir()
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[{core._now()}]\n{text}\n")
        except Exception:
            pass

    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        _write(text)
        try:
            messagebox.showerror("出现错误", f"{exc}\n\n详细日志：{log_path}", parent=root)
        except Exception:
            pass

    def callback_hook(exc_type, exc, tb):
        _write("".join(traceback.format_exception(exc_type, exc, tb)))

    sys.excepthook = hook
    root.report_callback_exception = callback_hook


def main() -> None:
    try:
        from tkinterdnd2 import TkinterDnD  # type: ignore
        root = TkinterDnD.Tk()
    except Exception:
        root = tk.Tk()

    # 先隐藏主窗，UI 控件全部构建完再显示，避免启动时出现空白窗。
    root.withdraw()
    root.title(f"{core.APP_NAME} · {core.APP_SUBTITLE}")
    root.configure(bg="#F4F6FB")
    ico = _resource(os.path.join("assets", "filekeeper.ico"))
    if os.path.exists(ico):
        try:
            root.iconbitmap(ico)
        except Exception:
            pass

    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w = min(1200, max(1020, sw - 60))
    h = min(880, max(700, sh - 110))
    x, y = max(0, (sw - w) // 2), max(0, (sh - h) // 2 - 20)
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.minsize(1020, 700)

    from . import license as _lic
    from . import registration as _reg
    version = _lic.VERSION
    try:
        allowed, _msg = _reg.gate(root, version)
    except Exception as exc:  # noqa: BLE001
        allowed = False
        messagebox.showerror("注册校验失败", f"无法校验授权：{exc}\n\n请检查网络后重试。", parent=root)
    if not allowed:
        try:
            root.destroy()
        except Exception:
            pass
        return

    app = FileKeeperApp(root)
    _install_error_hook(root)
    root.deiconify()
    root.lift()
    root.mainloop()


if __name__ == "__main__":
    main()

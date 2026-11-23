# -*- coding: utf-8 -*-
"""文文界面层。"""

from __future__ import annotations

import datetime as _dt
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from PIL import Image, ImageTk

from . import core, invoice as invoice_mod

FONT = "微软雅黑"
MONO = "Consolas"
BG = "#F4F6FB"
CARD = "#FFFFFF"
ACCENT = "#2563EB"
ACCENT_DARK = "#1D4ED8"
TEXT = "#111827"
MUTED = "#6B7280"
BORDER = "#E3E8F0"
OK = "#15803D"
WARN = "#D97706"
DANGER = "#DC2626"
SOFT_BLUE = "#EEF4FF"
SOFT_GREY = "#F3F4F6"

# 五个主页面的低饱和配色：main=主色，bg=浅底，hover=悬停底，border=浅边框，strong=按下/深色
NAV_COLORS: Dict[str, Dict[str, str]] = {
    "inbox": {"main": "#1D4ED8", "strong": "#1E40AF", "bg": "#EAF2FF",
              "hover": "#DCE9FF", "border": "#BFDBFE"},
    "folders": {"main": "#0F766E", "strong": "#0B5F59", "bg": "#E7F8F4",
                "hover": "#D2F1E9", "border": "#A7E3D9"},
    "records": {"main": "#7C3AED", "strong": "#6D28D9", "bg": "#F1EAFE",
                "hover": "#E6D8FD", "border": "#D8C2FA"},
    "search": {"main": "#B45309", "strong": "#92400E", "bg": "#FFF5DF",
               "hover": "#FDE9BF", "border": "#F5D48A"},
    "invoices": {"main": "#BE123C", "strong": "#9F1239", "bg": "#FFEAF0",
                 "hover": "#FFD8E2", "border": "#F8B4C8"},
}


def _asset_path(name: str) -> str:
    """源码运行时取项目 assets；PyInstaller 打包后取 _MEIPASS。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", name)


def _open_path(path: str) -> None:
    if not path:
        return
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except Exception:
        try:
            subprocess.Popen(["explorer", path])
        except Exception:
            pass


def _reveal(path: str) -> None:
    if not path:
        return
    try:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    except Exception:
        _open_path(os.path.dirname(path))


def _is_invoice_analysis(a: Dict[str, Any]) -> bool:
    """行程单等交通票据带有 invoice 字段，但只有真实发票才计入台账。"""
    if "is_invoice" in a:
        return bool(a.get("is_invoice"))
    return bool(a.get("invoice"))


def _descendants(widget: tk.Misc) -> List[tk.Misc]:
    out: List[tk.Misc] = []
    for child in widget.winfo_children():
        out.append(child)
        out.extend(_descendants(child))
    return out


class FileKeeperApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        core.init_db()
        self.cfg = core.load_config()
        self.presets = core.load_presets()
        self.current = core.get_preset(self.presets, self.cfg.get("preset_id", "project"))
        self.analysis: Optional[Dict[str, Any]] = None
        self.batch: List[Dict[str, Any]] = []
        self.busy = False
        self._bg_queue: "queue.Queue[tuple]" = queue.Queue()
        self.search_var = tk.StringVar()
        self.keyword_var = tk.StringVar()
        self.filter_var = tk.StringVar(value="全部分类")
        self.status_var = tk.StringVar(value="就绪 · 把文件拖到上方虚线区域")
        self.root_var = tk.StringVar(value=self.cfg.get("archive_root", core.default_root()))
        self.preset_var = tk.StringVar(value=self.current["name"])
        self.title_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self._nav_buttons: Dict[str, tk.Button] = {}
        self._nav_styles: Dict[str, dict] = {}
        self._pages: Dict[str, tk.Frame] = {}
        self._logo_photos: List[ImageTk.PhotoImage] = []
        self._auth_syncing = False
        self._auth_locked = False
        self._last_auth_sync = time.monotonic()

        self._setup_style()
        self._build_header()
        self._build_nav()
        self._build_body()
        self._build_statusbar()
        self._show_page("inbox")
        self._refresh_recent()
        self._refresh_stats()
        self.root.after(80, self._poll_bg)
        self.root.after(1200, self._sync_brand_logo)

    # ------------------------------------------------------------ 样式
    def _setup_style(self) -> None:
        self.root.configure(bg=BG)
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", font=(FONT, 10), background=CARD, foreground=TEXT)
        style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                        rowheight=30, borderwidth=0, font=(FONT, 10))
        style.configure("Treeview.Heading", background=SOFT_GREY, foreground=TEXT,
                        font=(FONT, 10, "bold"), borderwidth=0, relief="flat", padding=6)
        style.map("Treeview", background=[("selected", SOFT_BLUE)],
                  foreground=[("selected", ACCENT)], borderwidth=[("selected", 0)])
        style.map("Treeview.Heading", background=[("active", "#EAEFF7")])
        style.configure("TCombobox", padding=6, borderwidth=1, relief="flat",
                        fieldbackground=CARD, arrowsize=14)
        style.map("TCombobox", fieldbackground=[("readonly", CARD)],
                  bordercolor=[("focus", ACCENT)])
        style.configure("TEntry", padding=7, borderwidth=1, relief="flat")
        style.configure("TCheckbutton", background=CARD, font=(FONT, 10))
        style.configure("TRadiobutton", background=CARD, font=(FONT, 10))
        style.configure("TScrollbar", background=SOFT_GREY, arrowsize=12, borderwidth=0)

    # ------------------------------------------------------------ 组件工具
    def _tone_for(self, widget: tk.Misc) -> Optional[str]:
        """沿父级向上查找页面配色标记，页面内按钮自动继承色系。"""
        cur: Optional[tk.Misc] = widget
        while cur is not None:
            tone = getattr(cur, "_fk_tone", None)
            if tone in NAV_COLORS:
                return str(tone)
            cur = getattr(cur, "master", None)
        return None

    def _button(self, parent, text: str, cmd: Callable, kind: str = "primary",
                width: Optional[int] = None, font_size: int = 10,
                tone: Optional[str] = None) -> tk.Button:
        tone = tone or self._tone_for(parent)
        if kind == "danger":
            palette = ("#FFFFFF", "#FEF2F2", DANGER, DANGER, "#FCA5A5")
        elif kind == "success":
            palette = (OK, "#166534", "#FFFFFF", "#FFFFFF", OK)
        elif tone in NAV_COLORS:
            c = NAV_COLORS[tone]
            if kind == "primary":
                palette = (c["main"], c["strong"], "#FFFFFF", "#FFFFFF", c["main"])
            elif kind == "secondary":
                palette = (c["bg"], c["hover"], c["main"], c["main"], c["border"])
            else:  # ghost：白底彩色字，轻量但仍有页面色
                palette = ("#FFFFFF", c["bg"], c["main"], c["main"], c["border"])
        else:
            palette = {
                "primary": (ACCENT, ACCENT_DARK, "#FFFFFF", ACCENT_DARK, ACCENT),
                "secondary": ("#F3F5F9", "#E4E9F2", "#374151", TEXT, "#D5DCE8"),
                "ghost": (CARD, SOFT_GREY, "#4B5563", TEXT, "#DDE3EC"),
            }[kind]
        bg, hover, fg, active_fg, border = palette
        b = tk.Button(
            parent, text=text, command=cmd, bg=bg, fg=fg, activebackground=hover,
            activeforeground=active_fg, bd=0, relief="flat", cursor="hand2",
            font=(FONT, font_size, "bold" if kind == "primary" else "normal"),
            padx=16, pady=7, width=width, highlightthickness=1,
            highlightbackground=border,
        )
        b.bind("<Enter>", lambda _e: b.configure(bg=hover))
        b.bind("<Leave>", lambda _e: b.configure(bg=bg))
        return b

    def _card(self, parent, pad: int = 16) -> tk.Frame:
        outer = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        inner = tk.Frame(outer, bg=CARD)
        inner.pack(fill="both", expand=True, padx=pad, pady=pad)
        return inner

    def _label(self, parent, text: str, size: int = 10, color: str = TEXT,
               bold: bool = False, bg: str = CARD, **kw) -> tk.Label:
        return tk.Label(parent, text=text, font=(FONT, size, "bold" if bold else "normal"),
                        bg=bg, fg=color, **kw)

    def _section_title(self, parent, title: str, sub: str = "", bg: str = CARD) -> tk.Frame:
        box = tk.Frame(parent, bg=bg)
        self._label(box, title, 13, TEXT, True, bg=bg).pack(side="left")
        if sub:
            self._label(box, sub, 9, MUTED, bg=bg).pack(side="left", padx=(10, 0), pady=(3, 0))
        return box

    # ------------------------------------------------------------ 头部 + 导航
    def _logo_photo(self, path: str, height: int = 38) -> Optional[ImageTk.PhotoImage]:
        try:
            im = Image.open(path).convert("RGBA")
            im.thumbnail((320, height), Image.LANCZOS)
            return ImageTk.PhotoImage(im)
        except Exception:
            return None

    def _logo_source(self) -> str:
        custom = core.LOGO_PATH
        if os.path.isfile(custom):
            return custom
        remote = os.path.join(core.APP_DIR, "brand_logo.png")
        if os.path.isfile(remote):
            return remote
        return _asset_path("logo.png")

    def _sync_brand_logo(self) -> None:
        """后台拉取服务端品牌图，不阻塞启动，也不覆盖用户本机自定义 Logo。"""
        def work() -> None:
            try:
                from . import license as _lic
                if _lic.fetch_brand_logo():
                    self._post(self._apply_logo)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def _apply_logo(self) -> None:
        photo = self._logo_photo(self._logo_source(), 38)
        if photo:
            self._logo_photos = [photo]
            self.logo_label.configure(image=photo, text="", bg=CARD)
        else:
            self._logo_photos = []
            self.logo_label.configure(image="", text=core.APP_NAME, bg=ACCENT,
                                      fg="#FFFFFF", font=(FONT, 15, "bold"),
                                      padx=10, pady=4)

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=CARD, height=62, highlightthickness=1,
                          highlightbackground=BORDER)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        self.logo_label = tk.Label(header, bg=CARD, bd=0, padx=0, pady=0)
        self.logo_label.pack(side="left", padx=(18, 10))
        self._apply_logo()
        self._label(header, core.APP_SUBTITLE, 9, MUTED).pack(side="left", padx=(2, 0))

        right = tk.Frame(header, bg=CARD)
        right.pack(side="right", padx=(0, 18))
        self._button(right, "设置", self._open_settings, "ghost", font_size=9,
                     tone="inbox").pack(side="right")
        self._button(right, "使用教程", self._open_guide, "ghost", font_size=9,
                     tone="records").pack(side="right", padx=(0, 6))
        rootbox = tk.Frame(right, bg=SOFT_BLUE, cursor="hand2", highlightthickness=1,
                           highlightbackground="#C7D9FB", padx=10, pady=4)
        rootbox.pack(side="right", padx=(0, 10))
        self.root_label = tk.Label(rootbox, text="", font=(FONT, 9, "bold"), bg=SOFT_BLUE,
                                   fg=ACCENT_DARK, cursor="hand2")
        self.root_label.pack(anchor="w")
        self._set_root_label()
        change = tk.Label(rootbox, text="更改目录", font=(FONT, 8), bg=SOFT_BLUE,
                          fg=MUTED, cursor="hand2")
        change.pack(anchor="w")
        # 整块区域可点：标题、路径、子标签全部绑定「打开」；右键/「更改目录」换目录
        for w in _descendants(rootbox) + [rootbox]:
            w.configure(cursor="hand2")
            w.bind("<Button-1>", lambda _e: self._open_root())
            w.bind("<Button-3>", lambda _e: self._change_root())
        change.configure(cursor="hand2")
        change.unbind("<Button-1>")
        change.bind("<Button-1>", lambda _e: self._change_root())

    def _set_root_label(self) -> None:
        path = self.root_var.get().strip() or "未设置"
        # 不用 emoji：Tk 在 Windows 上首次测量 emoji 目录文字可阻塞约 1 秒。
        self.root_label.configure(text="打开归档目录 · " + self._short_path(path, 38))

    def _open_guide(self) -> None:
        """在系统浏览器打开图文使用教程。"""
        try:
            webbrowser.open("https://sw.olilily.com/guide/")
        except Exception:
            messagebox.showwarning("使用教程", "暂时无法打开教程，请访问 sw.olilily.com/guide/")

    def _build_nav(self) -> None:
        nav = tk.Frame(self.root, bg=BG)
        nav.pack(fill="x", padx=18, pady=(12, 8))
        items = [("inbox", "拖入归档"), ("folders", "建文件夹"),
                 ("records", "存档记录"), ("search", "搜索找文件"), ("invoices", "发票台账")]
        # 五个入口各用一组低饱和色：默认浅底彩字，悬停加深，选中用主色填充白字。
        for key, text in items:
            c = NAV_COLORS[key]
            fg, bg, hover, border = c["main"], c["bg"], c["hover"], c["border"]
            self._nav_styles[key] = {"fg": fg, "bg": bg, "hover": hover, "border": border}
            holder = tk.Frame(nav, bg=BG)
            holder.pack(side="left", padx=(0, 8))
            # 用 Button 而不是 Label：Label 在部分 Windows/Tk 组合下只触发悬停，
            # 鼠标按下事件不落到命令上，用户会看到“点不动”的假象。
            btn = tk.Button(
                holder, text=text, command=lambda k=key: self._show_page(k),
                font=(FONT, 10, "bold"), bg=bg, fg=fg, activebackground=hover,
                activeforeground=fg, padx=16, pady=7, cursor="hand2", bd=0,
                relief="flat", overrelief="flat", takefocus=False,
                highlightthickness=1, highlightbackground=border)
            btn.pack()
            self._nav_buttons[key] = btn
            btn.bind("<Enter>", lambda _e, k=key: self._hover_nav(k, True))
            btn.bind("<Leave>", lambda _e, k=key: self._hover_nav(k, False))
        self._active_page = ""
        # 键盘快捷键：Ctrl+1~5 对应五个主页，便于键盘用户和不便拖拽的场景。
        for i, (key, _text) in enumerate(items, start=1):
            self.root.bind(f"<Control-Key-{i}>",
                           lambda _e, k=key: self._show_page(k))

    def _hover_nav(self, key: str, enter: bool) -> None:
        if key == self._active_page:
            return
        s = self._nav_styles[key]
        self._nav_buttons[key].configure(
            bg=s["hover"] if enter else s["bg"],
            fg=s["fg"], highlightbackground=s["border"])

    def _show_page(self, key: str) -> None:
        for k, page in self._pages.items():
            page.pack_forget()
            s = self._nav_styles[k]
            self._nav_buttons[k].configure(
                bg=s["bg"], fg=s["fg"], font=(FONT, 10, "bold"),
                highlightbackground=s["border"])
        self._pages[key].pack(fill="both", expand=True, padx=18, pady=12)
        s = self._nav_styles[key]
        self._nav_buttons[key].configure(
            bg=s["fg"], fg="#FFFFFF", font=(FONT, 10, "bold"),
            highlightbackground=s["fg"])
        self._active_page = key
        if key == "records":
            self._refresh_records()
        if key == "search":
            self.ent_search.focus_set()
        if key == "invoices":
            self._refresh_invoices()

    def _build_body(self) -> None:
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)
        for key in ("inbox", "folders", "records", "search", "invoices"):
            page = tk.Frame(body, bg=BG)
            page._fk_tone = key  # 页面内按钮继承该页配色
            self._pages[key] = page
        self._build_inbox(self._pages["inbox"])
        self._build_folders(self._pages["folders"])
        self._build_records(self._pages["records"])
        self._build_search(self._pages["search"])
        self._build_invoices(self._pages["invoices"])

    # ------------------------------------------------------------ 页面 1：拖入归档
    def _build_inbox(self, page: tk.Frame) -> None:
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=0)
        page.rowconfigure(2, weight=0)
        page.rowconfigure(3, weight=1)

        toolbar = tk.Frame(page, bg=BG)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._label(toolbar, "归档方案", 10, MUTED, bg=BG).pack(side="left")
        self.preset_box = ttk.Combobox(toolbar, textvariable=self.preset_var, state="readonly",
                                       width=26, values=[p["name"] for p in self.presets])
        self.preset_box.pack(side="left", padx=(8, 16))
        self.preset_box.bind("<<ComboboxSelected>>", self._on_preset_change)
        self._label(toolbar, "拖入后按方案里的关键词自动判断归属", 9, MUTED, bg=BG).pack(side="left")
        self._button(toolbar, "打开根目录", self._open_root, "ghost",
                     font_size=9).pack(side="right")
        self._button(toolbar, "选择文件", self._pick_files, "secondary",
                     font_size=9).pack(side="right", padx=(0, 8))

        # 拖放区
        self.drop = tk.Canvas(page, bg=CARD, height=120, highlightthickness=1,
                              highlightbackground=BORDER, cursor="hand2")
        self.drop.grid(row=1, column=0, sticky="nsew")
        self.drop.bind("<Configure>", lambda _e: self._draw_drop())
        self.drop.bind("<Button-1>", lambda _e: self._pick_files())
        self.drop.bind("<Enter>", lambda _e: self._drop_hover(True))
        self.drop.bind("<Leave>", lambda _e: self._drop_hover(False))
        self._register_dnd()
        self._draw_drop()

        # 识别结果卡片
        result_wrap = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        result_wrap.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        result = tk.Frame(result_wrap, bg=CARD)
        result.pack(fill="both", expand=True, padx=16, pady=8)
        result.columnconfigure(0, weight=1)
        result.columnconfigure(1, weight=0, minsize=420)
        result.rowconfigure(2, weight=1)

        head = tk.Frame(result, bg=CARD)
        head.grid(row=0, column=0, columnspan=2, sticky="ew")
        self._section_title(head, "识别结果", "修改标题或分类后点击归档").pack(side="left")
        self.conf_badge = tk.Label(head, text="等待文件", bg=SOFT_GREY, fg=MUTED,
                                   font=(FONT, 9), padx=10, pady=3)
        self.conf_badge.pack(side="right")
        self.dup_label = tk.Label(head, text="", bg="#FEF2F2", fg="#B91C1C",
                                  font=(FONT, 9), padx=8, pady=3)

        left = tk.Frame(result, bg=CARD)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 20), pady=(10, 0))
        right = tk.Frame(result, bg=CARD)
        right.grid(row=1, column=1, sticky="nsew", pady=(10, 0))
        result.rowconfigure(1, weight=1)

        self.file_head = self._label(left, "把文件拖到上面，或点击选择文件", 12, TEXT, True)
        self.file_head.pack(anchor="w")
        self.file_meta = self._label(left, "支持 Word / PDF / Excel / 图片 / 文本 / 压缩包等，可多选或拖整个文件夹",
                                     9, MUTED)
        self.file_meta.pack(anchor="w", pady=(3, 8))

        title_row = tk.Frame(left, bg=CARD)
        title_row.pack(fill="x", pady=(0, 8))
        self._label(title_row, "标题", 9, MUTED).pack(side="left", padx=(0, 8))
        self.ent_title = ttk.Entry(title_row, textvariable=self.title_var)
        self.ent_title.pack(side="left", fill="x", expand=True)
        self.title_var.trace_add("write", lambda *_: self._update_target_hint())

        self._label(left, "内容摘要", 9, MUTED).pack(anchor="w")
        self.txt_excerpt = tk.Text(left, height=2, bd=0, bg=SOFT_GREY, fg="#374151",
                                   font=(FONT, 9), wrap="word", padx=10, pady=8,
                                   relief="flat", cursor="arrow", highlightthickness=1,
                                   highlightbackground=SOFT_GREY)
        self.txt_excerpt.pack(fill="both", expand=True, pady=(4, 0))
        self.txt_excerpt.insert("1.0", "拖入文件后，这里会显示识别到的标题与内容摘要…")
        self.txt_excerpt.configure(state="disabled", fg=MUTED)

        self._label(right, "归档到分类", 9, MUTED).pack(anchor="w")
        self.cat_box = ttk.Combobox(right, textvariable=self.category_var, state="readonly",
                                    values=[f["name"] for f in self.current["folders"]])
        self.cat_box.pack(fill="x", pady=(4, 10))
        self.cat_box.bind("<<ComboboxSelected>>", lambda _e: self._update_target_hint())

        tags_row = tk.Frame(right, bg=CARD)
        tags_row.pack(fill="x", pady=(0, 8))
        self._label(tags_row, "标签", 9, MUTED).pack(side="left", padx=(0, 8))
        self.tags_var = tk.StringVar()
        ttk.Entry(tags_row, textvariable=self.tags_var).pack(side="left", fill="x", expand=True)
        self._label(tags_row, "逗号分隔", 8, MUTED).pack(side="left", padx=(6, 0))

        self._label(right, "目标位置", 9, MUTED).pack(anchor="w")
        self.target_label = self._label(right, "—", 9, "#334155", bg=SOFT_GREY,
                                        justify="left", anchor="w", wraplength=360)
        self.target_label.pack(fill="x", pady=(4, 8), ipady=5, ipadx=8)

        action_row = tk.Frame(right, bg=CARD)
        action_row.pack(fill="x", side="bottom")
        self.btn_archive = self._button(action_row, "归档到此处", self._do_archive, "primary")
        self.btn_archive.pack(side="left")
        self._button(action_row, "忽略", self._clear_result, "ghost").pack(side="left", padx=(8, 0))

        mode_row = tk.Frame(right, bg=CARD)
        mode_row.pack(fill="x", side="bottom", pady=(0, 6))
        self._label(mode_row, "归档方式", 9, MUTED).pack(side="left", padx=(0, 4))
        self.arch_action = tk.StringVar(value="复制" if self.cfg.get("action") == "copy" else "移动")
        for text, val in (("复制", "复制"), ("移动", "移动")):
            tk.Radiobutton(mode_row, text=text, variable=self.arch_action, value=val,
                           bg=CARD, activebackground=CARD, selectcolor="#FFFFFF",
                           font=(FONT, 9), bd=0, highlightthickness=0, cursor="hand2",
                           command=self._on_action_change).pack(side="left", padx=(0, 4))

        # 最近归档
        recent = tk.Frame(page, bg=BG)
        recent.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        recent_head = tk.Frame(recent, bg=BG)
        recent_head.pack(fill="x")
        self._label(recent_head, "最近归档", 10, TEXT, True, bg=BG).pack(side="left")
        self._label(recent_head, "Ctrl / Shift 可多选", 9, MUTED, bg=BG).pack(side="left", padx=(8, 0))
        self.btn_recent_del = self._button(
            recent_head, "批量删除", lambda: self._bulk_delete(self.tree_recent),
            "danger", font_size=9, tone="inbox")
        self.btn_recent_del.pack(side="right", padx=(8, 0))
        self.lbl_recent = self._label(recent_head, "", 9, MUTED, bg=BG)
        self.lbl_recent.pack(side="right")

        cols = ("time", "name", "cat", "size")
        self.tree_recent = ttk.Treeview(recent, columns=cols, show="headings", height=3,
                                        selectmode="extended")
        for c, t, w in zip(cols, ("归档时间", "文件名", "分类", "大小"), (130, 420, 160, 90)):
            self.tree_recent.heading(c, text=t)
            self.tree_recent.column(c, width=w, anchor="w" if c != "size" else "e")
        self.tree_recent.pack(fill="both", expand=True, pady=(6, 0))
        self.tree_recent.bind("<Double-1>", lambda _e: self._open_selected(self.tree_recent))
        self.tree_recent.bind("<Control-a>", lambda _e: self._select_all(self.tree_recent))
        self.tree_recent.bind("<Button-3>", self._recent_menu)
        page.rowconfigure(3, weight=1)

        self._update_target_hint()

    def _draw_drop(self, hover: bool = False) -> None:
        c = self.drop
        c.delete("all")
        w, h = max(c.winfo_width(), 240), max(c.winfo_height(), 110)
        color = ACCENT if hover else "#C7D2FE"
        c.create_rectangle(12, 12, w - 12, h - 12, outline=color, width=2, dash=(7, 5))
        cx, cy = w / 2, h / 2
        c.create_oval(cx - 21, cy - 58, cx + 21, cy - 16, fill=SOFT_BLUE, outline="")
        c.create_text(cx, cy - 37, text="↑", font=(FONT, 16, "bold"), fill=ACCENT)
        c.create_text(cx, cy + 8, text="把文件拖到这里", font=(FONT, 14, "bold"), fill=TEXT)
        c.create_text(cx, cy + 34,
                      text="也可以点击此区域选择文件   ·   支持一次拖入多个文件或整个文件夹",
                      font=(FONT, 9), fill=MUTED)

    def _drop_hover(self, enter: bool) -> None:
        self._draw_drop(hover=enter)

    def _register_dnd(self) -> None:
        try:
            from tkinterdnd2 import DND_FILES  # type: ignore
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", self._on_drop)
            self.dnd_ready = True
        except Exception:
            self.dnd_ready = False

    def _on_drop(self, event) -> None:
        try:
            paths = list(self.root.tk.splitlist(event.data))
        except Exception:
            paths = [event.data.strip("{}")]
        self._handle_paths([p.strip("{}") for p in paths if p])

    def _pick_files(self) -> None:
        paths = filedialog.askopenfilenames(title="选择要归档的文件")
        if paths:
            self._handle_paths(list(paths))

    def _handle_paths(self, paths: List[str]) -> None:
        if self.busy:
            self._set_status("正在处理上一个文件，请稍候…", WARN)
            return
        max_files = core.MAX_BATCH_FILES
        files: List[str] = []
        for p in paths:
            if os.path.isdir(p):
                count = 0
                for dirpath, _dirs, names in os.walk(p):
                    for n in names:
                        files.append(os.path.join(dirpath, n))
                        count += 1
                        if count > max_files:
                            break
                    if count > max_files:
                        break
            elif os.path.isfile(p):
                files.append(p)
            if len(files) > max_files:
                break

        # 去重：同名文件只算一个，避免重复归档
        unique: List[str] = []
        seen = set()
        for f in files:
            key = os.path.normcase(os.path.abspath(f))
            if key in seen:
                continue
            seen.add(key)
            unique.append(f)
        total = len(unique)

        if total == 0:
            messagebox.showwarning("没有可用文件", "没有找到可归档的文件。")
            return
        if total > max_files:
            messagebox.showwarning(
                "超过单次上限",
                f"一次最多识别并归档 {max_files} 个文件。\n"
                f"这次选择了 {total} 个（含文件夹里的文件），请分批拖入。")
            self._set_status(f"文件过多：{total} 个，单次上限 {max_files} 个", WARN)
            return

        if total > 1:
            self._set_status(f"正在分析 {total} 个文件…", WARN)
        else:
            self._set_status("正在分析文件内容…", WARN)
        self.busy = True
        preset = self.current
        self._run_bg(
            lambda: [core.analyze_file(f, preset) for f in unique],
            lambda results: self._on_analyzed(results),
        )

    def _on_analyzed(self, results: List[Dict[str, Any]]) -> None:
        self.busy = False
        if not results:
            return
        if len(results) == 1:
            self._show_result(results[0])
            self._set_status("识别完成，确认分类后归档", OK)
        else:
            self._open_batch(results)

    def _open_batch(self, results: List[Dict[str, Any]]) -> None:
        self._set_status(f"识别完成：{len(results)} 个文件，确认后批量归档", OK)
        BatchDialog(self, results)

    def _show_result(self, a: Dict[str, Any]) -> None:
        self.analysis = a
        self.file_head.configure(text=a["name"])
        type_tail = " · 类型已纠正" if a.get("type_mismatch") else ""
        self.file_meta.configure(
            text=f'{a["kind"] or a["ext"]}{type_tail} · {core.human_size(a["size"])} · 修改于 {a["mtime"]}'
        )
        self.title_var.set(a["title"])
        if a.get("invoice") and a.get("suggest_name"):
            self.title_var.set(os.path.splitext(a["suggest_name"])[0])
        self.cat_box.configure(values=[f["name"] for f in self.current["folders"]])
        self.category_var.set(a["category"])
        self.txt_excerpt.configure(state="normal")
        self.txt_excerpt.delete("1.0", "end")
        self.txt_excerpt.insert("1.0", a.get("excerpt") or "（未提取到正文，已按文件名和类型判断）")
        self.txt_excerpt.configure(state="disabled", fg="#374151")
        conf = int(a.get("confidence", 0) * 100)
        color = OK if conf >= 70 else (WARN if conf >= 45 else MUTED)
        level = "高" if conf >= 70 else ("中" if conf >= 45 else "低")
        self.conf_badge.configure(text=f"识别置信度 {conf}% · {level}", bg="#ECFDF5" if conf >= 70
                                  else ("#FFF7ED" if conf >= 45 else SOFT_GREY),
                                  fg=color)
        self._update_target_hint()
        dup = a.get("duplicate")
        inv_dup = a.get("invoice_duplicate")
        if dup:
            self.dup_label.configure(
                text=f"库内已有相同文件：{dup.get('name', '')}（{dup.get('category', '')}）")
            self.dup_label.pack(side="right", padx=(0, 8))
        elif inv_dup:
            self.dup_label.configure(
                text=f"疑似重复发票：台账已有 #{inv_dup.get('id', '')}"
                     f" {inv_dup.get('inv_date', '')} ¥{float(inv_dup.get('amount') or 0):.2f}"
                     f"（同样会归档，仅作提醒）")
            self.dup_label.pack(side="right", padx=(0, 8))
        else:
            self.dup_label.pack_forget()
        alts = [x for x in (a.get("alternatives") or []) if isinstance(x, dict)][:2]
        alt_txt = ("   备选 " + " / ".join(f'{x["folder"]}({x["score"]})' for x in alts)) if alts else ""
        self._set_status(f'{a["reason"]} · 建议 {a["category"]}{alt_txt}', OK)

    def _update_target_hint(self) -> None:
        a = self.analysis
        cat = self.category_var.get() or "99_待分类"
        title = (self.title_var.get() or "").strip()
        if a:
            stem = os.path.splitext(a["name"])[0]
            name = (title if title and title != a["title"] else stem) + a["ext"]
            if self.cfg.get("date_prefix"):
                name = _dt.datetime.now().strftime("%Y%m%d_") + name
            parts = [self.root_var.get(), cat]
            if self.cfg.get("month_folder"):
                parts.append(_dt.datetime.now().strftime("%Y-%m"))
            parts.append(core.safe_name(name))
            self.target_label.configure(text=os.path.join(*parts))
        else:
            self.target_label.configure(text="—")

    def _on_action_change(self) -> None:
        self.cfg["action"] = "copy" if self.arch_action.get() == "复制" else "move"
        core.save_config(self.cfg)

    def _do_archive(self) -> None:
        if not self.analysis:
            messagebox.showinfo("还没有文件", "请先拖入或选择一个文件。")
            return
        self._archive_many([(self.analysis, self.category_var.get(),
                             (self.title_var.get() or "").strip(),
                             (self.tags_var.get() or "").strip())], refresh_detail=True)

    def _archive_many(self, items: List[tuple], refresh_detail: bool = False,
                      subfolder: Optional[str] = None) -> None:
        root = self._ensure_root()
        if not root:
            return
        if subfolder is None:      # 未显式指定时，发票默认按「日期_张数_金额」建汇总文件夹
            invs = [it[0]["invoice"] for it in items
                    if _is_invoice_analysis(it[0]) and invoice_mod.is_invoice_folder(it[1] or "")]
            subfolder = invoice_mod.batch_folder_name(invs) if invs else ""
        dups = [it for it in items if (it[0].get("invoice_duplicate"))]
        if dups and not messagebox.askyesno(
                "疑似重复发票",
                f"这批文件里有 {len(dups)} 张发票与台账已有记录同号或同日同额：\n\n"
                + "\n".join(f'· {it[0]["name"][:46]}' for it in dups[:5])
                + "\n\n仍要归档吗？（会归档并标记为「重复」，方便你人工核对）"):
            self._set_status("已取消归档", MUTED)
            return
        action = "move" if self.arch_action.get() == "移动" else "copy"
        date_prefix = bool(self.cfg.get("date_prefix"))
        month_folder = bool(self.cfg.get("month_folder"))
        self._set_status("正在归档…", WARN)

        def work():
            done = []
            for item in items:
                a, cat, title = item[0], item[1], item[2]
                tags = item[3] if len(item) > 3 else ""
                if title and title != a.get("title"):
                    a = dict(a, title=title)
                    if a.get("corrected_name"):
                        a["corrected_name"] = title + a.get("ext", "")
                if a.get("invoice") and title:
                    a = dict(a, suggest_name=title + a.get("ext", ""))
                suggest = a.get("_suggest") or a.get("category")
                if cat and cat != suggest:
                    try:
                        core.learn_correction(self.current, a, cat)
                    except Exception:
                        pass
                use_sub = subfolder if (_is_invoice_analysis(a)
                                        and invoice_mod.is_invoice_folder(cat or "")) else ""
                done.append(core.archive_file(a, cat, root, action, date_prefix,
                                              tags=tags, month_folder=month_folder,
                                              subfolder=use_sub))
            return done

        self.busy = True
        self._run_bg(work, lambda recs: self._after_archive(recs, refresh_detail))

    def _after_archive(self, recs: List[Dict[str, Any]], refresh_detail: bool) -> None:
        self.busy = False
        self._refresh_recent()
        self._refresh_stats()
        if refresh_detail:
            self.analysis = None
            self._clear_result()
        if recs:
            first = recs[0]
            self._set_status(f'已归档 {len(recs)} 个文件 → {first["category"]}', OK)
        dup_n = 0
        try:
            dup_n = core.invoice_dup_count_for([r["id"] for r in recs])
        except Exception:
            dup_n = 0
        if dup_n:
            self._set_status(f"已归档 {len(recs)} 个文件，其中 {dup_n} 张是疑似重复发票（台账已标黄）", WARN)
        if self.cfg.get("open_after_archive") and recs:
            _open_path(recs[0]["folder"])
        if len(recs) > 1:
            msg = f"已归档 {len(recs)} 个文件。"
            if dup_n:
                msg += f"\n\n注意：{dup_n} 张发票与已有记录重复，已在发票台账标记。"
            messagebox.showinfo("归档完成", msg + "\n可在「存档记录」里查看或导出 Excel。")
        elif not refresh_detail:
            self._clear_result()

    def _clear_result(self) -> None:
        self.analysis = None
        self.file_head.configure(text="把文件拖到上面，或点击选择文件")
        self.file_meta.configure(text="支持 Word / PDF / Excel / 图片 / 文本 / 压缩包等，可多选或拖整个文件夹")
        self.title_var.set("")
        self.category_var.set("")
        self.tags_var.set("")
        self.dup_label.pack_forget()
        self.conf_badge.configure(text="等待文件", bg=SOFT_GREY, fg=MUTED)
        self.txt_excerpt.configure(state="normal")
        self.txt_excerpt.delete("1.0", "end")
        self.txt_excerpt.insert("1.0", "拖入文件后，这里会显示识别到的标题与内容摘要…")
        self.txt_excerpt.configure(state="disabled", fg=MUTED)
        self.target_label.configure(text="—")
        self._set_status("就绪 · 把文件拖到上方虚线区域", MUTED)

    def _refresh_recent(self) -> None:
        for i in self.tree_recent.get_children():
            self.tree_recent.delete(i)
        rows = core.all_records(limit=3)
        for r in rows:
            self.tree_recent.insert("", "end", iid=str(r["id"]),
                                    values=((r["archived_at"] or "")[:16], r["name"], r["category"],
                                            core.human_size(r["size"])))
        if rows:
            self.lbl_recent.configure(text=f'累计 {core.stats()["count"]} 个文件 · '
                                           f'{core.human_size(core.stats()["size"])}')
        else:
            self.lbl_recent.configure(text="")

    # ------------------------------------------------------------ 页面 2：建文件夹
    def _build_folders(self, page: tk.Frame) -> None:
        page.columnconfigure(0, weight=3, uniform="col")
        page.columnconfigure(1, weight=2, uniform="col")
        page.rowconfigure(0, weight=1)

        left = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        lp = tk.Frame(left, bg=CARD)
        lp.pack(fill="both", expand=True, padx=18, pady=16)

        self._section_title(lp, "按方案批量建目录", "先预览，再创建，不会覆盖已有文件夹").pack(anchor="w")

        row1 = tk.Frame(lp, bg=CARD)
        row1.pack(fill="x", pady=(12, 6))
        self._label(row1, "方案", 10, MUTED).pack(side="left")
        self.folder_preset_var = tk.StringVar(value=self.current["name"])
        self.folder_preset = ttk.Combobox(row1, textvariable=self.folder_preset_var, state="readonly",
                                          values=[p["name"] for p in self.presets])
        self.folder_preset.pack(side="left", padx=(8, 0), fill="x", expand=True)
        self.folder_preset.bind("<<ComboboxSelected>>", lambda _e: self._refresh_folder_preview())

        row2 = tk.Frame(lp, bg=CARD)
        row2.pack(fill="x", pady=(6, 4))
        self._label(row2, "根目录", 10, MUTED).pack(side="left")
        self.folder_root_var = tk.StringVar(value=self.cfg.get("archive_root", core.default_root()))
        ttk.Entry(row2, textvariable=self.folder_root_var).pack(side="left", fill="x", expand=True, padx=8)
        self._button(row2, "浏览", self._pick_folder_root, "secondary", font_size=9).pack(side="left")

        self.lbl_preset_desc = self._label(lp, self.current.get("desc", ""), 9, MUTED)
        self.lbl_preset_desc.pack(anchor="w", pady=(6, 8))

        preview_head = tk.Frame(lp, bg=CARD)
        preview_head.pack(fill="x")
        self._label(preview_head, "目录预览", 9, MUTED).pack(side="left")
        self.lbl_preview_count = self._label(preview_head, "", 9, ACCENT)
        self.lbl_preview_count.pack(side="left", padx=(8, 0))

        tree_wrap = tk.Frame(lp, bg=CARD)
        tree_wrap.pack(fill="both", expand=True, pady=(6, 10))
        self.tree_preview = ttk.Treeview(tree_wrap, columns=("folder", "keywords", "status"),
                                         show="headings", height=7)
        self.tree_preview.heading("folder", text="文件夹")
        self.tree_preview.heading("keywords", text="自动识别关键词")
        self.tree_preview.heading("status", text="状态")
        self.tree_preview.column("folder", width=190)
        self.tree_preview.column("keywords", width=330)
        self.tree_preview.column("status", width=80, anchor="center")
        self.tree_preview.tag_configure("ok", foreground=MUTED)
        self.tree_preview.tag_configure("new", foreground=ACCENT)
        self.tree_preview.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree_preview.yview)
        sb.pack(side="right", fill="y")
        self.tree_preview.configure(yscrollcommand=sb.set)

        opts = tk.Frame(lp, bg=CARD)
        opts.pack(fill="x", pady=(0, 8))
        self.open_after_create = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text="创建完成后打开根目录", variable=self.open_after_create,
                       bg=CARD, activebackground=CARD, selectcolor="#FFFFFF",
                       font=(FONT, 9), bd=0, highlightthickness=0, cursor="hand2").pack(side="left")

        act = tk.Frame(lp, bg=CARD)
        act.pack(fill="x")
        self._button(act, "生成这些文件夹", self._create_folders, "primary").pack(side="left")
        self._button(act, "只建空根目录", self._create_root_only, "secondary").pack(side="left", padx=(8, 0))
        self.lbl_create_log = self._label(act, "", 9, MUTED)
        self.lbl_create_log.pack(side="left", padx=(12, 0))

        # 右侧：自定义 + 模板管理
        right = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        right.grid(row=0, column=1, sticky="nsew")
        rp = tk.Frame(right, bg=CARD)
        rp.pack(fill="both", expand=True, padx=18, pady=16)
        self._section_title(rp, "自定义目录清单", "每行一个，支持 父/子 层级").pack(anchor="w")
        self.txt_custom = tk.Text(rp, height=9, bd=0, bg=SOFT_GREY, fg=TEXT, font=(FONT, 10),
                                  wrap="none", padx=10, pady=8, relief="flat")
        self.txt_custom.pack(fill="both", expand=True, pady=(10, 6))
        self.txt_custom.insert("1.0", "01_项目文档\n02_数据与报表\n03_Reports\n04_Deliverables\n99_待分类")
        self._label(rp, "提示：目录名可中文或英文（如 03_Reports）；自定义清单会建在当前根目录下", 8, MUTED).pack(anchor="w")
        self._button(rp, "按清单生成", self._create_custom_folders, "secondary").pack(anchor="w", pady=(8, 16))

        tk.Frame(rp, bg=BORDER, height=1).pack(fill="x", pady=(0, 14))
        self._section_title(rp, "方案模板", "可新建、修改、删除自己的方案").pack(anchor="w")
        btns = tk.Frame(rp, bg=CARD)
        btns.pack(fill="x", pady=(10, 0))
        self._button(btns, "新建方案", lambda: self._edit_preset(None), "ghost", font_size=9).pack(side="left")
        self._button(btns, "编辑当前", lambda: self._edit_preset(self.current), "ghost",
                     font_size=9).pack(side="left", padx=(8, 0))
        self._button(btns, "删除", self._delete_preset, "ghost", font_size=9).pack(side="left", padx=(8, 0))
        self._label(rp, "关键词决定自动归档去向；改完立即生效。", 8, MUTED).pack(anchor="w", pady=(10, 0))

        self._refresh_folder_preview()

    def _refresh_folder_preview(self) -> None:
        preset = core.get_preset(self.presets, self._preset_id_by_name(self.folder_preset_var.get()))
        self.folder_preset_var.set(preset["name"])
        self.lbl_preset_desc.configure(text=preset.get("desc", ""))
        for i in self.tree_preview.get_children():
            self.tree_preview.delete(i)
        root = self.folder_root_var.get().strip()
        if root:
            exists = os.path.isdir(root)
            self.tree_preview.insert("", "end", values=(os.path.basename(root) or root, "根目录",
                                                        "已存在" if exists else "待创建"),
                                     tags=("ok" if exists else "new",))
        for folder in preset.get("folders", []):
            kw = "、".join(folder.get("keywords", [])[:6]) or "（兜底分类）"
            exists = os.path.isdir(os.path.join(root, folder["name"])) if root else False
            self.tree_preview.insert("", "end", values=(folder["name"], kw,
                                                        "已存在" if exists else "待创建"),
                                     tags=("ok" if exists else "new",))
        self.lbl_preview_count.configure(
            text=f"共 {len(preset.get('folders', []))} 个文件夹")

    def _pick_folder_root(self) -> None:
        path = filedialog.askdirectory(title="选择建文件夹的根目录",
                                       initialdir=self.folder_root_var.get() or os.path.expanduser("~"))
        if path:
            self.folder_root_var.set(os.path.normpath(path))

    def _create_folders(self) -> None:
        root = self.folder_root_var.get().strip()
        if not root:
            messagebox.showwarning("缺少根目录", "请先选择根目录。")
            return
        preset = core.get_preset(self.presets, self._preset_id_by_name(self.folder_preset_var.get()))
        try:
            res = core.create_folders(root, [f["name"] for f in preset.get("folders", [])])
        except OSError as e:
            messagebox.showerror("创建失败", f"无法创建目录：{e}")
            return
        msg = f"新建 {len(res['created'])} 个，已存在 {len(res['existed'])} 个"
        if res["failed"]:
            msg += f"，失败 {len(res['failed'])} 个"
        self.lbl_create_log.configure(text=msg, fg=OK if not res["failed"] else DANGER)
        self._set_status(f"目录已生成：{root}（{msg}）", OK)
        if self.open_after_create.get():
            _open_path(root)
        self._refresh_folder_preview()

    def _create_root_only(self) -> None:
        root = self.folder_root_var.get().strip()
        if not root:
            return
        core.create_folders(root, [])
        self.lbl_create_log.configure(text="根目录已就绪", fg=OK)
        _open_path(root)

    def _create_custom_folders(self) -> None:
        root = self.folder_root_var.get().strip()
        if not root:
            messagebox.showwarning("缺少根目录", "请先选择根目录。")
            return
        lines = [ln.strip() for ln in self.txt_custom.get("1.0", "end").split("\n") if ln.strip()]
        if not lines:
            messagebox.showinfo("没有目录", "请先在清单里填写文件夹名。")
            return
        res = core.create_folders(root, lines)
        msg = f"新建 {len(res['created'])} 个，已存在 {len(res['existed'])} 个"
        self.lbl_create_log.configure(text=msg, fg=OK if not res["failed"] else DANGER)
        self._set_status(f"自定义目录已生成：{root}（{msg}）", OK)
        if self.open_after_create.get():
            _open_path(root)

    def _preset_id_by_name(self, name: str) -> str:
        for p in self.presets:
            if p.get("name") == name:
                return p["id"]
        return self.presets[0]["id"]

    def _edit_preset(self, preset: Optional[Dict[str, Any]]) -> None:
        PresetDialog(self, preset, self.presets, on_saved=self._after_preset_saved)

    def _delete_preset(self) -> None:
        preset = core.get_preset(self.presets, self._preset_id_by_name(self.folder_preset_var.get()))
        if len(self.presets) <= 1:
            messagebox.showinfo("无法删除", "至少保留一个方案。")
            return
        if not messagebox.askyesno("删除方案", f"确定删除方案「{preset['name']}」？"):
            return
        self.presets = [p for p in self.presets if p["id"] != preset["id"]]
        core.save_presets(self.presets)
        self.current = self.presets[0]
        self.cfg["preset_id"] = self.current["id"]
        core.save_config(self.cfg)
        self._reload_presets()

    def _after_preset_saved(self) -> None:
        self.presets = core.load_presets()
        self.current = core.get_preset(self.presets, self.cfg.get("preset_id", self.presets[0]["id"]))
        self._reload_presets()

    def _reload_presets(self) -> None:
        names = [p["name"] for p in self.presets]
        self.preset_box.configure(values=names)
        self.folder_preset.configure(values=names)
        self.preset_var.set(self.current["name"])
        self.folder_preset_var.set(self.current["name"])
        self.cat_box.configure(values=[f["name"] for f in self.current["folders"]])
        self._refresh_folder_preview()

    # ------------------------------------------------------------ 页面 3：存档记录
    def _build_records(self, page: tk.Frame) -> None:
        page.rowconfigure(3, weight=1)
        page.columnconfigure(0, weight=1)
        top = tk.Frame(page, bg=BG)
        top.grid(row=0, column=0, sticky="ew")
        self._section_title(top, "存档记录", "所有归档都有出处可查，可一键导出 Excel", bg=BG
                            ).pack(side="left")

        bar = tk.Frame(page, bg=BG)
        bar.grid(row=1, column=0, sticky="ew", pady=(10, 6))
        self._label(bar, "关键词", 9, MUTED, bg=BG).pack(side="left", padx=(0, 6))
        ent = ttk.Entry(bar, textvariable=self.keyword_var, width=28)
        ent.pack(side="left")
        ent.bind("<Return>", lambda _e: self._refresh_records())
        self._label(bar, "分类", 9, MUTED, bg=BG).pack(side="left", padx=(14, 6))
        self.cat_filter = ttk.Combobox(bar, textvariable=self.filter_var, state="readonly", width=15)
        self.cat_filter.pack(side="left")
        self.cat_filter.bind("<<ComboboxSelected>>", lambda _e: self._refresh_records())
        self._button(bar, "查询", self._refresh_records, "secondary", font_size=9).pack(side="left", padx=8)
        self._button(bar, "导出 Excel", self._export_excel, "primary", font_size=9).pack(side="right")

        bar2 = tk.Frame(page, bg=BG)
        bar2.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self._button(bar2, "撤销归档", lambda: self._undo_selected(), "ghost",
                     font_size=9).pack(side="left")
        self._button(bar2, "批量删除", lambda: self._bulk_delete(self.tree_records), "danger",
                     font_size=9).pack(side="left", padx=(6, 0))
        self._button(bar2, "全选", lambda: self._select_all(self.tree_records), "ghost",
                     font_size=9).pack(side="left", padx=(6, 0))
        self._button(bar2, "打开目录", lambda: self._reveal_selected(), "ghost",
                     font_size=9).pack(side="left", padx=(6, 0))
        self._button(bar2, "批量重命名", self._open_batch_rename, "secondary",
                     font_size=9).pack(side="left", padx=(6, 0))
        self._button(bar2, "补录为发票", self._manual_invoice, "secondary",
                     font_size=9).pack(side="left", padx=(6, 0))
        self._button(bar2, "撤销上一步", self._undo_last_action, "ghost",
                     font_size=9).pack(side="left", padx=(6, 0))
        self._button(bar2, "历史", self._open_undo_history, "ghost",
                     font_size=9).pack(side="left", padx=(6, 0))
        self._label(bar2, "Ctrl / Shift 多选", 9, MUTED, bg=BG).pack(side="right")

        table_wrap = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        table_wrap.grid(row=3, column=0, sticky="nsew")
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)
        cols = ("time", "name", "title", "cat", "size", "folder")
        self.tree_records = ttk.Treeview(table_wrap, columns=cols, show="headings",
                                         selectmode="extended")
        for c, t, w, anchor in zip(cols, ("归档时间", "文件名", "识别标题", "分类", "大小", "存放目录"),
                                   (182, 280, 240, 140, 90, 380), ("w", "w", "w", "w", "e", "w")):
            self.tree_records.heading(c, text=t)
            self.tree_records.column(c, width=w, minwidth=60, anchor=anchor, stretch=False)
        self.tree_records.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree_records.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.tree_records.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree_records.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree_records.tag_configure("odd", background="#FAFBFD")
        self.tree_records.bind("<Double-1>", lambda _e: self._open_selected(self.tree_records))
        self.tree_records.bind("<Button-3>", self._record_menu)
        self.tree_records.bind("<Control-a>", lambda _e: self._select_all(self.tree_records))
        self.tree_records.bind("<<TreeviewSelect>>", lambda _e: self._preview_from(self.tree_records))

        prev = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        prev.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self._build_preview(prev)

        foot = tk.Frame(page, bg=BG)
        foot.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        self.lbl_records_foot = self._label(foot, "", 9, MUTED, bg=BG)
        self.lbl_records_foot.pack(side="left")

    def _build_preview(self, parent: tk.Frame) -> None:
        box = tk.Frame(parent, bg=CARD)
        box.pack(fill="x", padx=12, pady=8)
        self.prev_canvas = tk.Canvas(box, bg=SOFT_GREY, width=220, height=150,
                                     highlightthickness=1, highlightbackground=BORDER, cursor="hand2")
        self.prev_canvas.pack(side="left")
        self.prev_canvas.bind("<Button-1>", lambda _e: self._open_prev())
        right = tk.Frame(box, bg=CARD)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.prev_name = self._label(right, "选中一条记录，这里显示缩略图和摘要", 10, TEXT, True)
        self.prev_name.pack(anchor="w")
        self.prev_meta = self._label(right, "", 9, MUTED, justify="left", wraplength=900)
        self.prev_meta.pack(anchor="w", pady=(4, 0))
        self._thumb_ref = None
        self._prev_path = ""

    def _open_prev(self) -> None:
        if self._prev_path and os.path.exists(self._prev_path):
            _open_path(self._prev_path)

    def _preview_from(self, tree: ttk.Treeview) -> None:
        sel = tree.selection()
        if not sel:
            return
        rec = core.get_record(int(sel[0]))
        if rec:
            self._render_preview(rec)

    def _render_preview(self, rec) -> None:
        path = rec["dst_path"] or ""
        self._prev_path = path
        self.prev_name.configure(text=rec["name"])
        meta = [f'{rec["category"]} · {core.human_size(rec["size"])} · {rec["archived_at"][:16]}']
        if rec["title"] and rec["title"] != os.path.splitext(rec["name"])[0]:
            meta.append(f'标题：{rec["title"]}')
        if rec["excerpt"]:
            meta.append(rec["excerpt"][:140].replace("\n", " "))
        self.prev_meta.configure(text="\n".join(meta))
        c = self.prev_canvas
        c.delete("all")
        self._thumb_ref = None
        ext = os.path.splitext(path)[1].lower()
        img = None
        try:
            if path and os.path.exists(path):
                from PIL import Image
                if ext in core.IMAGE_EXT:
                    img = Image.open(path)
                elif ext == ".pdf":
                    try:
                        import pymupdf
                    except Exception:
                        import fitz as pymupdf
                    doc = pymupdf.open(path)
                    pix = doc.load_page(0).get_pixmap(matrix=pymupdf.Matrix(1.2, 1.2))
                    import io
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    doc.close()
                if img is not None:
                    img.thumbnail((216, 146))
        except Exception:
            img = None
        if img is not None:
            try:
                from PIL import ImageTk
                self._thumb_ref = ImageTk.PhotoImage(img)
                c.create_image(110, 75, image=self._thumb_ref)
                return
            except Exception:
                pass
        c.create_text(110, 62, text=(ext.lstrip(".") or "文件").upper(), font=(FONT, 12, "bold"),
                      fill="#94A3B8")
        c.create_text(110, 84, text="无预览", font=(FONT, 8), fill="#94A3B8")

    def _refresh_records(self) -> None:
        cats = ["全部分类"] + [c["category"] for c in core.category_counts()]
        self.cat_filter.configure(values=cats)
        if self.filter_var.get() not in cats:
            self.filter_var.set("全部分类")
        kw = self.keyword_var.get().strip()
        rows = core.search_records(kw, "全部", limit=5000) if kw else core.all_records(limit=5000)
        want = self.filter_var.get()
        if want and want != "全部分类":
            rows = [r for r in rows if r["category"] == want]
        for i in self.tree_records.get_children():
            self.tree_records.delete(i)
        for idx, r in enumerate(rows):
            self.tree_records.insert("", "end", iid=str(r["id"]),
                                     values=((r["archived_at"] or "")[:16], r["name"], r["title"],
                                             r["category"], core.human_size(r["size"]), r["folder"]),
                                     tags=("odd",) if idx % 2 else ())
        total = sum(int(r["size"] or 0) for r in rows)
        self.lbl_records_foot.configure(text=f"共 {len(rows)} 条 · 合计 {core.human_size(total)}")

    def _selected_rows(self, tree: ttk.Treeview) -> List[int]:
        return [int(i) for i in tree.selection()]

    def _open_selected(self, tree: ttk.Treeview) -> None:
        sel = tree.selection()
        if not sel:
            return
        rec = core.get_record(int(sel[0]))
        if rec and rec["dst_path"] and os.path.exists(rec["dst_path"]):
            _open_path(rec["dst_path"])
        else:
            messagebox.showwarning("文件不存在", "文件可能已被移动或删除，可在搜索页更新索引。")

    def _reveal_selected(self) -> None:
        sel = self.tree_records.selection()
        if not sel:
            return
        rec = core.get_record(int(sel[0]))
        if rec:
            _reveal(rec["dst_path"])

    def _record_menu(self, event) -> None:
        iid = self.tree_records.identify_row(event.y)
        if not iid:
            return
        self.tree_records.selection_set(iid)
        rec = core.get_record(int(iid))
        menu = tk.Menu(self.root, tearoff=0, font=(FONT, 9))
        menu.add_command(label="打开文件", command=lambda: self._open_selected(self.tree_records))
        menu.add_command(label="打开所在文件夹", command=lambda: _reveal(rec["dst_path"]) if rec else None)
        menu.add_command(label="复制完整路径",
                         command=lambda: (self.root.clipboard_clear(),
                                          self.root.clipboard_append(rec["dst_path"])) if rec else None)
        menu.add_separator()
        menu.add_command(label="撤销归档（移回原位置）", command=self._undo_selected)
        menu.add_command(label="批量删除选中", command=lambda: self._bulk_delete(self.tree_records))
        menu.tk_popup(event.x_root, event.y_root)

    def _manual_invoice(self) -> None:
        sel = self.tree_records.selection()
        if not sel:
            messagebox.showinfo("先选记录", "请先在列表里选中那条没能识别的发票文件，再补录。")
            return
        rec = core.get_record(int(sel[0]))
        if not rec:
            return
        ManualInvoiceDialog(self, rec, self._after_manual_invoice)

    def _after_manual_invoice(self) -> None:
        self._refresh_records()
        try:
            self._refresh_invoices()
        except Exception:
            pass
        self._set_status("发票已补录台账，可在「发票台账」页标记已用/待用或导出", OK)

    def _delete_selected(self) -> None:
        self._bulk_delete(self.tree_records)

    def _select_all(self, tree: ttk.Treeview) -> str:
        items = tree.get_children()
        if items:
            tree.selection_set(items)
        return "break"

    def _recent_menu(self, event) -> None:
        iid = self.tree_recent.identify_row(event.y)
        if not iid:
            return
        if iid not in self.tree_recent.selection():
            self.tree_recent.selection_set(iid)
        rec = core.get_record(int(iid))
        menu = tk.Menu(self.root, tearoff=0, font=(FONT, 9))
        menu.add_command(label="打开文件", command=lambda: self._open_selected(self.tree_recent))
        menu.add_command(label="打开所在文件夹", command=lambda: _reveal(rec["dst_path"]) if rec else None)
        menu.add_separator()
        menu.add_command(label="批量删除选中", command=lambda: self._bulk_delete(self.tree_recent))
        menu.tk_popup(event.x_root, event.y_root)

    def _bulk_delete(self, tree: ttk.Treeview) -> None:
        ids = self._selected_rows(tree)
        if not ids:
            messagebox.showinfo("先选记录", "请先在列表里选中要删除的记录（Ctrl / Shift 可多选）。")
            return
        files = 0
        for i in ids:
            rec = core.get_record(i)
            if rec and rec["dst_path"] and os.path.exists(rec["dst_path"]):
                files += 1
        ans = messagebox.askyesnocancel(
            "批量删除",
            f"已选 {len(ids)} 条记录，其中 {files} 个归档文件存在。\n\n"
            "是 = 删除记录并删除归档文件\n否 = 只删除记录，文件保留\n取消 = 不操作")
        if ans is None:
            return
        removed = 0
        if ans:
            for i in ids:
                rec = core.get_record(i)
                if rec and rec["dst_path"] and os.path.exists(rec["dst_path"]):
                    try:
                        os.remove(rec["dst_path"])
                        removed += 1
                    except OSError:
                        pass
        core.delete_records(ids)
        self._refresh_records()
        self._refresh_recent()
        self._refresh_stats()
        try:
            self._refresh_invoices()
        except Exception:
            pass
        self._set_status(f"已删除 {len(ids)} 条记录" + (f"，同时删除 {removed} 个文件" if ans else "，文件已保留"), OK)

    def _undo_selected(self) -> None:
        ids = self._selected_rows(self.tree_records)
        if not ids:
            return
        if not messagebox.askyesno("撤销归档", "将把归档文件移回原位置（若原文件仍存在则只删副本），并删除记录。"):
            return
        for i in ids:
            rec = core.get_record(i)
            if not rec:
                continue
            try:
                core.undo_archive(rec, delete_file=not os.path.exists(rec["src_path"] or ""))
            except OSError:
                core.delete_records([i])
        self._refresh_records()
        self._refresh_recent()
        self._refresh_stats()

    def _export_excel(self) -> None:
        if not core.all_records(limit=1):
            messagebox.showinfo("还没有存档记录", "先归档几个文件，再来导出记录表。")
            return
        ExportDialog(self, self._export_to)

    def _export_to(self, path: str) -> None:
        self._set_status("正在导出 Excel…", WARN)
        rows = core.all_records(limit=50000)

        def work():
            try:
                core.export_excel(path, rows)
                return None
            except Exception as exc:  # noqa: BLE001
                return exc

        def done(err) -> None:
            if err is not None:
                self._set_status(f"导出失败：{err}", DANGER)
                messagebox.showerror(
                    "导出失败",
                    f"Excel 没有保存成功。\n\n目标：{path}\n原因：{err}\n\n"
                    "请确认目标文件夹可写，且同名文件没有被 Excel / WPS 打开。")
                return
            self._set_status(f"已导出：{path}", OK)
            if messagebox.askyesno("导出完成",
                                   f"已保存 {len(rows)} 条记录：\n{path}\n\n现在打开这份 Excel 吗？"):
                _open_path(path)

        self._run_bg(work, done)

    # ------------------------------------------------------------ 页面 4：搜索
    def _build_search(self, page: tk.Frame) -> None:
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)

        head = tk.Frame(page, bg=BG)
        head.grid(row=0, column=0, sticky="ew")
        self._section_title(head, "搜索找文件", "文件名、标题、正文摘要、分类都能搜", bg=BG).pack(side="left")
        self.lbl_index = self._label(head, "", 9, MUTED, bg=BG)
        self.lbl_index.pack(side="right")

        box = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        box.grid(row=1, column=0, sticky="ew", pady=(10, 10))
        inner = tk.Frame(box, bg=CARD)
        inner.pack(fill="x", padx=14, pady=12)
        self.ent_search = tk.Entry(inner, textvariable=self.search_var, bd=0, bg=SOFT_GREY,
                                   font=(FONT, 12), fg=TEXT, insertbackground=TEXT,
                                   highlightthickness=1, highlightbackground=BORDER,
                                   highlightcolor=ACCENT)
        self.ent_search.pack(side="left", fill="x", expand=True, ipady=8, padx=(10, 8))
        self.ent_search.bind("<Return>", lambda _e: self._do_search())
        self.search_scope = ttk.Combobox(inner, state="readonly", width=9,
                                         values=("全部", "文件名", "标题", "内容", "分类", "标签"))
        self.search_scope.set("全部")
        self.search_scope.pack(side="left", padx=(0, 8))
        self._button(inner, "搜索", self._do_search, "primary", font_size=10).pack(side="left")
        self._button(inner, "更新索引", self._index_now, "secondary", font_size=9).pack(side="left", padx=(8, 0))

        table_wrap = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        table_wrap.grid(row=2, column=0, sticky="nsew")
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)
        cols = ("name", "title", "cat", "size", "time", "path")
        self.tree_search = ttk.Treeview(table_wrap, columns=cols, show="headings")
        for c, t, w, a in zip(cols, ("文件名", "识别标题", "分类", "大小", "归档时间", "完整路径"),
                              (260, 230, 140, 85, 165, 350), ("w", "w", "w", "e", "w", "w")):
            self.tree_search.heading(c, text=t)
            self.tree_search.column(c, width=w, minwidth=60, anchor=a, stretch=False)
        self.tree_search.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree_search.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.tree_search.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree_search.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree_search.tag_configure("odd", background="#FAFBFD")
        self.tree_search.bind("<Double-1>", lambda _e: self._open_selected(self.tree_search))
        self.tree_search.bind("<Button-3>", self._search_menu)
        self.tree_search.bind("<<TreeviewSelect>>", lambda _e: self._preview_from(self.tree_search))

        prev = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        prev.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self._build_preview(prev)

        foot = tk.Frame(page, bg=BG)
        foot.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.lbl_search_foot = self._label(foot, "输入关键词后回车。找不到旧文件？点「更新索引」把归档目录扫描进数据库。",
                                           9, MUTED, bg=BG)
        self.lbl_search_foot.pack(side="left")

    def _do_search(self) -> None:
        kw = self.search_var.get().strip()
        rows = core.search_records(kw, self.search_scope.get(), limit=1000)
        for i in self.tree_search.get_children():
            self.tree_search.delete(i)
        for idx, r in enumerate(rows):
            self.tree_search.insert("", "end", iid=str(r["id"]),
                                    values=(r["name"], r["title"], r["category"],
                                            core.human_size(r["size"]), (r["archived_at"] or "")[:16],
                                            r["dst_path"]),
                                    tags=("odd",) if idx % 2 else ())
        self.lbl_search_foot.configure(
            text=f"找到 {len(rows)} 条结果" + ("" if kw else "（显示全部记录）"), fg=TEXT if rows else MUTED)
        if not rows:
            self.lbl_search_foot.configure(text="没有找到。可以试试更短的关键词，或先更新索引。", fg=WARN)

    def _search_menu(self, event) -> None:
        iid = self.tree_search.identify_row(event.y)
        if not iid:
            return
        self.tree_search.selection_set(iid)
        rec = core.get_record(int(iid))
        menu = tk.Menu(self.root, tearoff=0, font=(FONT, 9))
        menu.add_command(label="打开文件", command=lambda: self._open_selected(self.tree_search))
        menu.add_command(label="打开所在文件夹", command=lambda: _reveal(rec["dst_path"]) if rec else None)
        menu.add_command(label="复制路径", command=lambda: (self.root.clipboard_clear(),
                                                            self.root.clipboard_append(rec["dst_path"]))
                          if rec else None)
        menu.tk_popup(event.x_root, event.y_root)

    def _index_now(self) -> None:
        root = self._ensure_root()
        if not root:
            return
        if self.busy:
            self._set_status("正在处理其他任务…", WARN)
            return
        self.busy = True
        self._set_status(f"正在扫描 {root} …", WARN)
        self.lbl_index.configure(text="索引中…", fg=WARN)

        def work():
            return core.index_existing(
                root,
                progress=lambda n, p: self._post(
                    lambda n=n: self.lbl_index.configure(text=f"已索引 {n} 个文件…", fg=WARN)),
            )

        self._run_bg(work, self._after_index)

    def _after_index(self, added: int) -> None:
        self.busy = False
        st = core.stats()
        self.lbl_index.configure(text=f"索引完成 · 新增 {added} 条 · 库内 {st['count']} 条", fg=OK)
        self._set_status(f"索引完成，新增 {added} 个文件", OK)
        self._refresh_stats()
        self._refresh_recent()
        if self._active_page == "records":
            self._refresh_records()

    # ------------------------------------------------------------ 页面 5：发票台账
    def _build_invoices(self, page: tk.Frame) -> None:
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)

        head = tk.Frame(page, bg=BG)
        head.grid(row=0, column=0, sticky="ew")
        self._section_title(head, "发票台账", "自动识别日期、类别、销售方、金额；标记已用/待用", bg=BG
                            ).pack(side="left")
        self.lbl_inv_stats = self._label(head, "", 9, MUTED, bg=BG)
        self.lbl_inv_stats.pack(side="right")

        bar = tk.Frame(page, bg=BG)
        bar.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        self._label(bar, "状态", 9, MUTED, bg=BG).pack(side="left", padx=(0, 4))
        self.inv_filter = ttk.Combobox(bar, state="readonly", width=7,
                                       values=("全部", "待用", "已用"))
        self.inv_filter.set("全部")
        self.inv_filter.pack(side="left")
        self.inv_filter.bind("<<ComboboxSelected>>", lambda _e: self._refresh_invoices())
        self._label(bar, "类别", 9, MUTED, bg=BG).pack(side="left", padx=(10, 4))
        self.inv_cat = ttk.Combobox(bar, state="readonly", width=8, values=("全部类别",))
        self.inv_cat.set("全部类别")
        self.inv_cat.pack(side="left")
        self.inv_cat.bind("<<ComboboxSelected>>", lambda _e: self._refresh_invoices())
        self._label(bar, "月份", 9, MUTED, bg=BG).pack(side="left", padx=(10, 4))
        self.inv_month = ttk.Combobox(bar, state="readonly", width=9, values=("全部月份",))
        self.inv_month.set("全部月份")
        self.inv_month.pack(side="left")
        self.inv_month.bind("<<ComboboxSelected>>", lambda _e: self._refresh_invoices())
        self._label(bar, "搜索", 9, MUTED, bg=BG).pack(side="left", padx=(10, 4))
        self.inv_kw = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.inv_kw, width=14)
        ent.pack(side="left")
        ent.bind("<Return>", lambda _e: self._refresh_invoices())
        self._button(bar, "查询", self._refresh_invoices, "secondary", font_size=9).pack(side="left", padx=6)
        self._button(bar, "标记待用", lambda: self._mark_invoices("unused"), "ghost",
                     font_size=9).pack(side="right")
        self._button(bar, "标记已用", lambda: self._mark_invoices("used"), "ghost",
                     font_size=9).pack(side="right", padx=(0, 6))

        table_wrap = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        table_wrap.grid(row=2, column=0, sticky="nsew")
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)
        cols = ("status", "date", "cat", "seller", "amount", "no", "dup", "file")
        self.tree_inv = ttk.Treeview(table_wrap, columns=cols, show="headings")
        for c, t, w, a in zip(cols, ("状态", "开票日期", "类别", "销售方", "金额", "发票号码", "重复", "文件名"),
                              (56, 100, 66, 238, 92, 206, 48, 300),
                              ("center", "center", "center", "w", "e", "w", "center", "w")):
            self.tree_inv.heading(c, text=t)
            self.tree_inv.column(c, width=w, minwidth=44, anchor=a, stretch=False)
        self.tree_inv.grid(row=0, column=0, sticky="nsew")
        self.tree_inv.column("file", width=320, minwidth=180, stretch=True)
        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree_inv.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.tree_inv.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree_inv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree_inv.tag_configure("used", foreground="#94A3B8")
        self.tree_inv.tag_configure("odd", background="#FAFBFD")
        self.tree_inv.tag_configure("dup", background="#FFF7ED", foreground="#B45309")
        self.tree_inv.bind("<Double-1>", lambda _e: self._open_invoice())
        self.tree_inv.bind("<<TreeviewSelect>>", lambda _e: self._preview_invoice())

        bar2 = tk.Frame(page, bg=BG)
        bar2.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self._button(bar2, "打开文件", self._open_invoice, "secondary", font_size=9).pack(side="left")
        self._button(bar2, "打开所在目录", self._reveal_invoice, "ghost", font_size=9).pack(side="left", padx=(6, 0))
        self._button(bar2, "修改信息", self._edit_invoice, "ghost", font_size=9).pack(side="left", padx=(6, 0))
        self._button(bar2, "生成报销单 PDF", self._export_reimbursement, "primary", font_size=9).pack(side="right")
        self._button(bar2, "导出台账 Excel", self._export_invoices, "ghost", font_size=9).pack(side="right", padx=(0, 6))
        self._label(bar2, "筛选条件同时作用于导出", 9, MUTED, bg=BG).pack(side="right", padx=(0, 10))

        prev = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        prev.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self._build_preview(prev)

    def _inv_filters(self) -> Dict[str, str]:
        return {"status": self.inv_filter.get(), "keyword": self.inv_kw.get().strip(),
                "category": self.inv_cat.get(), "month": self.inv_month.get()}

    def _sync_inv_choices(self) -> None:
        cats = ["全部类别"] + core.invoice_categories()
        months = ["全部月份"] + core.invoice_months()
        self.inv_cat.configure(values=cats)
        self.inv_month.configure(values=months)
        if self.inv_cat.get() not in cats:
            self.inv_cat.set("全部类别")
        if self.inv_month.get() not in months:
            self.inv_month.set("全部月份")

    def _refresh_invoices(self) -> None:
        st = core.invoice_stats()
        dup = core.invoice_duplicate_count()
        self.lbl_inv_stats.configure(
            text=(f'共 {st["count"]} 张 · 合计 ¥{st["amount"]:.2f} ｜ '
                  f'待用 {st["unused"]} 张 ¥{st["unused_amount"]:.2f} ｜ '
                  f'已用 {st["used"]} 张 ¥{st["used_amount"]:.2f}'
                  + (f' ｜ 疑似重复 {dup} 张' if dup else '')))
        self._sync_inv_choices()
        f = self._inv_filters()
        rows = core.list_invoices(f["status"], f["keyword"], f["category"], f["month"])
        for i in self.tree_inv.get_children():
            self.tree_inv.delete(i)
        for idx, r in enumerate(rows):
            tags = []
            if r["status"] == "used":
                tags.append("used")
            if ("dup_flag" in r.keys() and r["dup_flag"]):
                tags.append("dup")
            elif idx % 2:
                tags.append("odd")
            self.tree_inv.insert("", "end", iid=str(r["id"]),
                                 values=("已用" if r["status"] == "used" else "待用",
                                         r["inv_date"], r["category"], r["seller"],
                                         f'{float(r["amount"] or 0):.2f}',
                                         ("\u200b" + r["invoice_no"]) if r["invoice_no"] else "",
                                         "重复" if tags and "dup" in tags else "",
                                         r["file_name"] or ""),
                                 tags=tuple(tags))
        if not rows and getattr(self, "_active_page", "") == "invoices":
            self._set_status("当前筛选下没有发票：把发票拖到「拖入归档」即可自动记账", MUTED)
        self._autosize_inv_columns()

    def _autosize_inv_columns(self) -> None:
        """按表头与内容实测像素宽度调整列宽，避免发票号码/销售方被截断。"""
        caps = {"status": 76, "date": 126, "cat": 94, "seller": 300,
                "amount": 106, "no": 258, "dup": 56, "file": 400}
        heads = ("状态", "开票日期", "类别", "销售方", "金额", "发票号码", "重复", "文件名")
        try:
            import tkinter.font as tkfont
            font = tkfont.Font(font=ttk.Style().lookup("Treeview", "font") or "TkDefaultFont")
        except Exception:
            import tkinter.font as tkfont
            font = tkfont.nametofont("TkDefaultFont")
        widths = {c: font.measure(h) + 30 for c, h in zip(
            ("status", "date", "cat", "seller", "amount", "no", "dup", "file"), heads)}
        for iid in self.tree_inv.get_children()[:300]:
            vals = self.tree_inv.item(iid, "values")
            for c, v in zip(("status", "date", "cat", "seller", "amount", "no", "dup", "file"), vals):
                widths[c] = max(widths[c], font.measure(str(v).replace("\u200b", "")) + 30)
        for c, w in widths.items():
            self.tree_inv.column(c, width=min(w, caps[c]))

    def _inv_ids(self) -> List[int]:
        return [int(i) for i in self.tree_inv.selection()]

    def _mark_invoices(self, status: str) -> None:
        ids = self._inv_ids()
        if not ids:
            self._set_status("先选中发票，再标记", WARN)
            return
        for i in ids:
            core.set_invoice_status(i, status)
        self._refresh_invoices()
        self._set_status(f"已标记 {len(ids)} 张为{'已用' if status == 'used' else '待用'}", OK)

    def _selected_invoice(self):
        ids = self._inv_ids()
        if not ids:
            return None
        with core._conn() as con:
            return con.execute("SELECT * FROM invoices WHERE id=?", (ids[0],)).fetchone()

    def _open_invoice(self) -> None:
        r = self._selected_invoice()
        if not r:
            return
        if os.path.exists(r["file_path"] or ""):
            _open_path(r["file_path"])
        else:
            messagebox.showwarning("文件不存在", "这张发票的文件可能已被移动或删除。")

    def _reveal_invoice(self) -> None:
        r = self._selected_invoice()
        if r:
            _reveal(r["file_path"])

    def _preview_invoice(self) -> None:
        r = self._selected_invoice()
        if r:
            rec = core.get_record(r["record_id"])
            if rec:
                self._render_preview(rec)

    def _edit_invoice(self) -> None:
        r = self._selected_invoice()
        if not r:
            return
        InvoiceEditDialog(self, r, self._after_invoice_edit)

    def _after_invoice_edit(self) -> None:
        self._refresh_invoices()
        if self._active_page == "records":
            self._refresh_records()

    def _export_invoices(self) -> None:
        f = self._inv_filters()
        if not core.list_invoices(f["status"], f["keyword"], f["category"], f["month"]):
            messagebox.showinfo("还没有发票", "当前筛选下没有发票可导出。")
            return
        ExportDialog(
            self, self._export_invoices_to, title="导出发票台账",
            default_name=f"发票台账_{_dt.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            hint="导出三张工作表：发票台账（含合计、重复标记与筛选）· 分类汇总（带图表）· 月度汇总。")

    def _export_invoices_to(self, path: str) -> None:
        self._set_status("正在导出发票台账…", WARN)
        f = self._inv_filters()
        rows = core.list_invoices(f["status"], f["keyword"], f["category"], f["month"])

        def work():
            try:
                return core.export_invoice_excel(path, rows, f["status"])
            except Exception as exc:  # noqa: BLE001
                return exc

        def done(res) -> None:
            if isinstance(res, Exception):
                self._set_status(f"导出失败：{res}", DANGER)
                messagebox.showerror("导出失败", f"台账没有保存成功。\n\n目标：{path}\n原因：{res}")
                return
            self._set_status(f"台账已导出：{res} 张发票 → {path}", OK)
            messagebox.showinfo("导出完成", f"已导出发票 {res} 张。\n\n{path}")

        self._run_bg(work, done)

    def _export_reimbursement(self) -> None:
        f = self._inv_filters()
        rows = core.list_invoices(f["status"], f["keyword"], f["category"], f["month"])
        if not rows:
            messagebox.showinfo("还没有发票", "当前筛选下没有发票，无法生成报销单。")
            return
        ReimbursementDialog(self, rows, f)

    def _export_reimbursement_to(self, path: str, rows, title: str, note: str) -> None:
        self._set_status("正在生成报销单 PDF…", WARN)

        def work():
            try:
                return core.export_reimbursement_pdf(path, rows, title, note)
            except Exception as exc:  # noqa: BLE001
                return exc

        def done(res) -> None:
            if isinstance(res, Exception):
                self._set_status(f"报销单生成失败：{res}", DANGER)
                messagebox.showerror("生成失败", f"原因：{res}")
                return
            self._set_status(f'报销单已生成：{res["count"]} 张发票 / {res["pages"]} 页 → {path}', OK)
            msg = f'报销单已生成：{res["count"]} 张发票，共 {res["pages"]} 页。\n\n{path}'
            if res["skipped"]:
                msg += f'\n\n有 {len(res["skipped"])} 个附件未能附上（见 PDF 末页）。'
                msg += "\n· " + "\n· ".join(res["skipped"][:5])
            if messagebox.askyesno("生成完成", msg + "\n\n现在打开查看吗？"):
                _open_path(path)

        self._run_bg(work, done)

    # ------------------------------------------------------------ 重命名 / 撤销
    def _open_batch_rename(self) -> None:
        rows = [dict(core.get_record(int(i))) for i in self.tree_records.selection() if core.get_record(int(i))]
        if not rows:
            rows = [dict(r) for r in core.all_records(limit=5000)]
        if not rows:
            messagebox.showinfo("没有记录", "先归档文件，再进行批量重命名。")
            return
        BatchRenameDialog(self, rows, bool(self.tree_records.selection()))

    def _undo_last_action(self) -> None:
        try:
            msg = core.undo_last()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("撤销失败", str(exc))
            return
        if not msg:
            messagebox.showinfo("没有可撤销的操作", "历史里没有未撤销的步骤。")
            return
        self._set_status(msg, OK)
        self._refresh_records()
        self._refresh_recent()
        self._refresh_stats()
        if self._active_page == "invoices":
            self._refresh_invoices()

    def _open_undo_history(self) -> None:
        UndoHistoryDialog(self, self._undo_last_action)

    # ------------------------------------------------------------ 设置 / 基建
    def _ensure_root(self) -> Optional[str]:
        root = self.root_var.get().strip()
        if not root:
            self._change_root()
            root = self.root_var.get().strip()
        if not root:
            return None
        try:
            os.makedirs(root, exist_ok=True)
        except OSError as e:
            messagebox.showerror("根目录不可用", f"无法创建归档根目录：{e}")
            return None
        return root

    def _open_root(self) -> None:
        root = self.root_var.get().strip()
        if not root:
            self._change_root()
            return
        if not os.path.isdir(root):
            if not messagebox.askyesno("目录不存在", f"归档根目录还不存在：\n{root}\n\n要现在创建并打开吗？"):
                return
            try:
                os.makedirs(root, exist_ok=True)
            except OSError as e:
                messagebox.showerror("无法创建根目录", str(e))
                return
            self._set_status(f"已创建归档根目录：{root}", OK)
        _open_path(root)
        self._set_status(f"已在资源管理器打开：{root}", OK)

    def _change_root(self) -> None:
        path = filedialog.askdirectory(title="选择归档根目录", initialdir=self.root_var.get() or None)
        if path:
            self.root_var.set(os.path.normpath(path))
            self.folder_root_var.set(os.path.normpath(path))
            self.cfg["archive_root"] = os.path.normpath(path)
            core.save_config(self.cfg)
            self._set_root_label()
            self._update_target_hint()
            self._set_status(f"归档根目录已切换：{path}", OK)

    def _open_settings(self) -> None:
        SettingsDialog(self, self.cfg, on_saved=self._after_settings)

    def _after_settings(self) -> None:
        self._apply_logo()
        self.root_var.set(self.cfg.get("archive_root", core.default_root()))
        self._set_root_label()
        self.arch_action.set("复制" if self.cfg.get("action") == "copy" else "移动")
        self._update_target_hint()

    def _on_preset_change(self, _event=None) -> None:
        self.current = core.get_preset(self.presets, self._preset_id_by_name(self.preset_var.get()))
        self.cfg["preset_id"] = self.current["id"]
        core.save_config(self.cfg)
        self.cat_box.configure(values=[f["name"] for f in self.current["folders"]])
        if self.analysis:
            preset = self.current
            path = self.analysis["path"]
            self._run_bg(lambda: core.analyze_file(path, preset), self._apply_reanalysis)
        self.folder_preset_var.set(self.current["name"])
        self._refresh_folder_preview()
        self._set_status(f"已切换归档方案：{self.current['name']}", OK)

    def _apply_reanalysis(self, a: Dict[str, Any]) -> None:
        if not self.analysis:
            return
        a["path"] = self.analysis["path"]
        self._show_result(a)

    def _short_path(self, path: str, limit: int) -> str:
        if len(path) <= limit:
            return path
        norm = path.replace("/", os.sep)
        parts = [p for p in norm.split(os.sep) if p]
        tail = os.sep.join(parts[-2:]) if len(parts) >= 2 else norm
        keep = max(6, limit - len(tail) - 4)
        head = norm[:keep]
        idx = head.rfind(os.sep)
        if idx > 0:
            head = head[:idx]
        return f"{head}{os.sep}…{os.sep}{tail}"

    def _run_bg(self, work: Callable[[], Any], on_done: Callable[[Any], None]) -> None:
        def runner():
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001
                self._bg_queue.put(("error", exc))
                return
            self._bg_queue.put(("done", result, on_done))

        threading.Thread(target=runner, daemon=True).start()

    def _post(self, fn: Callable[[], None]) -> None:
        """供后台线程安全地把 UI 更新交给主线程。"""
        self._bg_queue.put(("call", fn))

    def _poll_bg(self) -> None:
        try:
            while True:
                item = self._bg_queue.get_nowait()
                kind = item[0]
                if kind == "error":
                    self._on_bg_error(item[1])
                elif kind == "done":
                    item[2](item[1])
                elif kind == "call":
                    item[1]()
        except queue.Empty:
            pass
        try:
            self.root.after(80, self._poll_bg)
        except tk.TclError:
            pass

    def _on_bg_error(self, exc: Exception) -> None:
        self.busy = False
        self._set_status(f"出错：{exc}", DANGER)
        messagebox.showerror("操作失败", str(exc))

    def _refresh_stats(self) -> None:
        st = core.stats()
        self.lbl_stats.configure(text=f"已归档 {st['count']} 个 · {core.human_size(st['size'])}")
        self.lbl_index.configure(text=f"库内 {st['count']} 条记录", fg=MUTED)

    def _set_status(self, text: str, color: str = MUTED) -> None:
        self.status_var.set(text)
        self.lbl_status.configure(fg=color)

    def _build_statusbar(self) -> None:
        bar = tk.Frame(self.root, bg=CARD, height=30, highlightthickness=1,
                       highlightbackground=BORDER)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.lbl_status = tk.Label(bar, textvariable=self.status_var, bg=CARD, fg=MUTED,
                                   font=(FONT, 9), anchor="w")
        self.lbl_status.pack(side="left", padx=16)
        self.lbl_auth = tk.Label(bar, text="", bg=CARD, fg=WARN, font=(FONT, 9))
        self.lbl_auth.pack(side="right", padx=(12, 0))
        self.btn_auth = tk.Label(bar, text="注册 / 续费", bg=CARD, fg=ACCENT, font=(FONT, 9),
                                 cursor="hand2")
        self.btn_auth.pack(side="right", padx=(10, 16))
        self.btn_auth.bind("<Button-1>", lambda _e: self._open_registration())
        self.lbl_stats = tk.Label(bar, text="", bg=CARD, fg=MUTED, font=(FONT, 9))
        self.lbl_stats.pack(side="right", padx=16)
        self._refresh_auth()

        self.root.bind("<Control-f>", lambda _e: (self._show_page("search"), self.ent_search.focus_set()))
        self.root.bind("<F5>", lambda _e: (self._refresh_records(), self._refresh_recent(), self._refresh_stats()))

    def _update_auth_label(self) -> None:
        try:
            from . import license as _lic
            self.lbl_auth.configure(text=_lic.summary_line(),
                                    fg=OK if _lic.evaluate()["valid"] else DANGER)
        except Exception:
            self.lbl_auth.configure(text="授权状态未知", fg=WARN)

    def _sync_auth_async(self) -> None:
        """运行中每 6 小时联网复核一次，避免长期挂着旧缓存绕过停用/到期。"""
        if self._auth_syncing or self._auth_locked:
            return
        self._auth_syncing = True
        self._last_auth_sync = time.monotonic()

        def worker() -> None:
            try:
                from . import license as _lic
                _lic.sync(_lic.VERSION)
            except Exception:
                pass
            finally:
                self._auth_syncing = False
                try:
                    self.root.after(0, self._after_auth_synced)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _after_auth_synced(self) -> None:
        """联网复核完成：先刷新标签；授权已失效则立即锁屏，要求续费。"""
        self._update_auth_label()
        if self._auth_locked:
            return
        try:
            from . import license as _lic
            valid = bool(_lic.evaluate()["valid"])
        except Exception:
            return
        if not valid:
            self._lock_for_auth()

    def _lock_for_auth(self) -> None:
        """运行中授权失效：弹注册/续费窗口；未恢复有效授权则退出程序。"""
        if self._auth_locked:
            return
        self._auth_locked = True
        try:
            self.root.bell()
        except Exception:
            pass
        try:
            from . import registration as _reg
            from . import license as _lic
            dlg = _reg.RegistrationDialog(self.root, _lic.VERSION)
            self.root.wait_window(dlg)
            if _lic.evaluate()["valid"]:
                self._auth_locked = False
                self._last_auth_sync = time.monotonic()
                self._update_auth_label()
                try:
                    self.root.after(60000, self._refresh_auth)
                except Exception:
                    pass
                return
        except Exception:
            pass
        try:
            messagebox.showwarning(
                "授权已失效",
                "授权已停用或到期，程序将退出。请重新启动后完成续费。")
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _refresh_auth(self) -> None:
        if self._auth_locked:
            return
        self._update_auth_label()
        if time.monotonic() - self._last_auth_sync >= 6 * 3600:
            self._sync_auth_async()
        try:
            self.root.after(60000, self._refresh_auth)
        except Exception:
            pass

    def _open_registration(self) -> None:
        try:
            from . import registration as _reg
            from . import license as _lic
            dlg = _reg.RegistrationDialog(self.root, _lic.VERSION)
            self.root.wait_window(dlg)
        except Exception as exc:  # noqa: BLE001
            messagebox.showwarning("注册窗口打不开", str(exc))
        self._refresh_auth()


# ================================================================ 对话框
class PresetDialog(tk.Toplevel):
    def __init__(self, app: FileKeeperApp, preset: Optional[Dict[str, Any]],
                 presets: List[Dict[str, Any]], on_saved: Callable):
        super().__init__(app.root)
        self.app = app
        self.preset = preset
        self.presets = presets
        self.on_saved = on_saved
        self.title("编辑方案" if preset else "新建方案")
        self.geometry("620x620")
        self.configure(bg=CARD)
        self.transient(app.root)
        self.grab_set()
        self.resizable(True, True)

        pad = tk.Frame(self, bg=CARD)
        pad.pack(fill="both", expand=True, padx=20, pady=18)
        tk.Label(pad, text="方案名称", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.name_var = tk.StringVar(value=(preset or {}).get("name", ""))
        ttk.Entry(pad, textvariable=self.name_var).pack(fill="x", pady=(4, 12))
        tk.Label(pad, text="一句话说明", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.desc_var = tk.StringVar(value=(preset or {}).get("desc", ""))
        ttk.Entry(pad, textvariable=self.desc_var).pack(fill="x", pady=(4, 12))

        head = tk.Frame(pad, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text="分类目录与关键词", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left")
        tk.Label(head, text="格式：文件夹名 | 关键词1,关键词2（文件夹名中英文均可）", bg=CARD, fg=ACCENT,
                 font=(FONT, 9)).pack(side="right")
        self.txt = tk.Text(pad, height=18, bd=0, bg=SOFT_GREY, font=(FONT, 9), wrap="word",
                           padx=10, pady=8)
        self.txt.pack(fill="both", expand=True, pady=(6, 10))
        if preset:
            self.txt.insert("1.0", "\n".join(
                f'{f["name"]} | ' + ",".join(f.get("keywords", [])) for f in preset.get("folders", [])
            ))
        else:
            self.txt.insert("1.0", "01_项目文档 | 需求,方案,报告\n02_数据 | 数据,csv,报表\n99_待分类 | ")

        foot = tk.Frame(pad, bg=CARD)
        foot.pack(fill="x")
        self.app._button(foot, "保存", self._save, "primary").pack(side="right")
        self.app._button(foot, "取消", self.destroy, "ghost").pack(side="right", padx=(0, 8))

    def _save(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("缺少名称", "请填写方案名称。", parent=self)
            return
        folders = []
        for line in self.txt.get("1.0", "end").split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("|", 1)
            fname = parts[0].strip()
            kws = []
            if len(parts) > 1:
                kws = [k.strip() for k in parts[1].replace("，", ",").split(",") if k.strip()]
            if not fname:
                continue
            parts = [p for p in fname.replace("\\", "/").split("/") if p]
            if (not parts or fname.startswith(("/", "\\")) or os.path.isabs(fname)
                    or any(p in (".", "..") for p in parts)):
                messagebox.showwarning("目录名不合法", f"「{fname}」不是合法的分类目录名，不能以 / 或 \\ 开头，也不能包含 . 或 .. 路径段。", parent=self)
                return
            folders.append({"name": fname, "keywords": kws})
        if not folders:
            messagebox.showwarning("缺少目录", "请至少填写一个分类目录。", parent=self)
            return
        if not any(f["name"].startswith("99") or "待分类" in f["name"] for f in folders):
            folders.append({"name": "99_待分类", "keywords": []})

        if self.preset:
            self.preset["name"] = name
            self.preset["desc"] = self.desc_var.get().strip()
            self.preset["folders"] = folders
        else:
            pid = f"custom_{int(_dt.datetime.now().timestamp())}"
            self.presets.append({"id": pid, "name": name,
                                 "desc": self.desc_var.get().strip(), "folders": folders})
        core.save_presets(self.presets)
        self.on_saved()
        self.destroy()


class ExportDialog(tk.Toplevel):
    """应用内导出面板：目录、文件名、结果都在界面上，避免系统另存为框的误操作。"""

    BAD_CHARS = set('\\/:*?"<>|')

    def __init__(self, app: FileKeeperApp, on_export: Callable[[str], None],
                 title: str = "导出存档记录",
                 default_name: str = "",
                 hint: str = "导出三张工作表：存档记录 · 分类统计 · 概览；生成 .xlsx，可直接用 Excel / WPS 打开。"):
        super().__init__(app.root)
        self.app = app
        self.on_export = on_export
        self.title(title)
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()

        pad = tk.Frame(self, bg=CARD)
        pad.pack(fill="both", expand=True, padx=26, pady=(22, 18))

        tk.Label(pad, text="保存到文件夹", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        row = tk.Frame(pad, bg=CARD)
        row.pack(fill="x", pady=(5, 14))
        self.dir_var = tk.StringVar(value=self._default_dir(app.cfg))
        self.dir_entry = ttk.Entry(row, textvariable=self.dir_var)
        app._button(row, "新建文件夹", self._mkdir, "secondary", font_size=9).pack(side="right")
        app._button(row, "选择", self._browse, "secondary", font_size=9).pack(side="right", padx=(0, 6))
        self.dir_entry.pack(side="left", fill="x", expand=True)

        tk.Label(pad, text="文件名", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.name_var = tk.StringVar(
            value=default_name or f"文件存档记录_{_dt.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
        ttk.Entry(pad, textvariable=self.name_var).pack(fill="x", pady=(5, 10))

        tk.Label(pad, text=hint, bg=CARD, fg=MUTED, font=(FONT, 8), wraplength=600,
                 justify="left").pack(anchor="w")

        self.lbl_msg = tk.Label(pad, text="", bg=CARD, fg=DANGER, font=(FONT, 9),
                                wraplength=600, justify="left")
        self.lbl_msg.pack(anchor="w", pady=(8, 0))

        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=(12, 10))
        foot = tk.Frame(pad, bg=CARD)
        foot.pack(fill="x")
        app._button(foot, "开始导出", self._export, "primary").pack(side="right")
        app._button(foot, "取消", self.destroy, "ghost").pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _e: self._export())
        self.bind("<Escape>", lambda _e: self.destroy())

        self.update_idletasks()
        w, h = 660, max(self.winfo_reqheight(), 260)
        x = app.root.winfo_rootx() + (app.root.winfo_width() - w) // 2
        y = app.root.winfo_rooty() + 110
        self.geometry(f"{w}x{h}+{max(x, 10)}+{max(y, 10)}")

    @staticmethod
    def _default_dir(cfg: Dict[str, Any]) -> str:
        saved = (cfg.get("export_dir") or "").strip()
        if saved and os.path.isdir(saved):
            return saved
        desk = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.isdir(desk):
            return desk
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        return docs if os.path.isdir(docs) else os.path.expanduser("~")

    def _browse(self) -> None:
        p = filedialog.askdirectory(title="选择导出目录", initialdir=self.dir_var.get() or None,
                                    parent=self)
        if p:
            self.dir_var.set(os.path.normpath(p))

    def _mkdir(self) -> None:
        from tkinter import simpledialog
        name = simpledialog.askstring("新建文件夹", "文件夹名称：", parent=self)
        if not name:
            return
        name = name.strip()
        if not name or set(name) & self.BAD_CHARS or name in (".", ".."):
            self.lbl_msg.configure(text="文件夹名不能为空，也不能是 . / ..，或包含 \\ / : * ? \" < > |")
            return
        base = self.dir_var.get().strip().strip('"')
        if not base or os.path.exists(base) and not os.path.isdir(base):
            self.lbl_msg.configure(text="请先填写一个可用的保存文件夹。")
            return
        path = os.path.join(base, name)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            self.lbl_msg.configure(text=f"创建文件夹失败：{exc}")
            return
        self.dir_var.set(path)
        self.lbl_msg.configure(text="")

    def _export(self) -> None:
        d = self.dir_var.get().strip().strip('"')
        if not d:
            self.lbl_msg.configure(text="请填写或选择保存文件夹。")
            return
        d = os.path.expanduser(os.path.expandvars(d))
        if os.path.exists(d) and not os.path.isdir(d):
            self.lbl_msg.configure(text="这个路径是一个文件，不是文件夹。")
            return
        if not os.path.isdir(d):
            try:
                os.makedirs(d)
            except OSError as exc:
                self.lbl_msg.configure(text=f"无法创建文件夹：{exc}")
                return

        name = self.name_var.get().strip()
        if not name:
            self.lbl_msg.configure(text="请填写文件名。")
            return
        if set(name) & self.BAD_CHARS:
            self.lbl_msg.configure(text="文件名不能包含 \\ / : * ? \" < > |")
            return
        if not name.lower().endswith(".xlsx"):
            name += ".xlsx"
        target = os.path.join(d, name)
        if os.path.exists(target) and not messagebox.askyesno(
                "文件已存在", f"同名文件已存在：\n{target}\n\n要覆盖它吗？", parent=self):
            return

        self.app.cfg["export_dir"] = d
        try:
            core.save_config(self.app.cfg)
        except OSError:
            pass
        self.destroy()
        self.on_export(target)


class ReimbursementDialog(tk.Toplevel):
    """生成报销单 PDF：选范围、填标题与备注、落盘。"""

    BAD_CHARS = set('\\/:*?"<>|')

    def __init__(self, app: FileKeeperApp, rows: List[Dict[str, Any]],
                 filters: Dict[str, str]):
        super().__init__(app.root)
        self.app = app
        self.all_rows = rows
        self.title("生成报销单 PDF")
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()

        pad = tk.Frame(self, bg=CARD)
        pad.pack(fill="both", expand=True, padx=26, pady=(20, 16))

        self.scope = tk.StringVar(value="filtered")
        head = tk.Frame(pad, bg=CARD)
        head.pack(fill="x", pady=(0, 12))
        tk.Label(head, text="报销范围", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left")
        ttk.Radiobutton(head, text=f"当前筛选（{len(rows)} 张）", value="filtered",
                        variable=self.scope, command=self._update_preview).pack(side="left", padx=(10, 12))
        ttk.Radiobutton(head, text="全部待用发票", value="unused",
                        variable=self.scope, command=self._update_preview).pack(side="left")

        self.summary_rows = rows
        self.lbl_sum = tk.Label(pad, text="", bg=CARD, fg=MUTED, font=(FONT, 9), justify="left")
        self.lbl_sum.pack(anchor="w", pady=(0, 12))

        tk.Label(pad, text="报销单标题", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.title_var = tk.StringVar(value="费用报销单")
        ttk.Entry(pad, textvariable=self.title_var).pack(fill="x", pady=(4, 10))

        tk.Label(pad, text="备注（部门 / 项目 / 报销人，可留空）", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.note_var = tk.StringVar()
        ttk.Entry(pad, textvariable=self.note_var).pack(fill="x", pady=(4, 12))

        tk.Label(pad, text="保存到文件夹", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        row = tk.Frame(pad, bg=CARD)
        row.pack(fill="x", pady=(4, 10))
        self.dir_var = tk.StringVar(value=ExportDialog._default_dir(app.cfg))
        self.dir_entry = ttk.Entry(row, textvariable=self.dir_var)
        app._button(row, "选择", self._browse, "secondary", font_size=9).pack(side="right")
        self.dir_entry.pack(side="left", fill="x", expand=True)

        tk.Label(pad, text="文件名", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.name_var = tk.StringVar(
            value=f"报销单_{filters.get('month', '全部月份')}_{_dt.datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
        ttk.Entry(pad, textvariable=self.name_var).pack(fill="x", pady=(4, 10))

        tk.Label(pad, text="首页为汇总表（张数 / 合计 / 明细），随后逐张附上发票原件；"
                           "扫描件与照片会转成整页图片，PDF 则原样拼接。",
                 bg=CARD, fg=MUTED, font=(FONT, 8), wraplength=600, justify="left").pack(anchor="w")

        self.lbl_msg = tk.Label(pad, text="", bg=CARD, fg=DANGER, font=(FONT, 9),
                                wraplength=600, justify="left")
        self.lbl_msg.pack(anchor="w", pady=(6, 0))

        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=(10, 8))
        foot = tk.Frame(pad, bg=CARD)
        foot.pack(fill="x")
        app._button(foot, "生成 PDF", self._go, "primary").pack(side="right")
        app._button(foot, "取消", self.destroy, "ghost").pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _e: self.destroy())
        self._update_preview()
        self.update_idletasks()
        w, h = 660, max(self.winfo_reqheight(), 420)
        x = app.root.winfo_rootx() + (app.root.winfo_width() - w) // 2
        y = app.root.winfo_rooty() + 90
        self.geometry(f"{w}x{h}+{max(x, 10)}+{max(y, 10)}")

    def _update_preview(self) -> None:
        if self.scope.get() == "unused":
            self.summary_rows = core.list_invoices("待用", "", "全部类别", "全部月份")
        else:
            self.summary_rows = self.all_rows
        total = sum(float(r["amount"] or 0) for r in self.summary_rows)
        missing = sum(1 for r in self.summary_rows if not os.path.exists(r["file_path"] or ""))
        cats = sorted({r["category"] for r in self.summary_rows if r["category"]})
        txt = f'共 {len(self.summary_rows)} 张 · 合计 ¥{total:.2f}'
        if cats:
            txt += " · " + "、".join(cats[:6])
        if missing:
            txt += f'\n其中 {missing} 张原件找不到，只会计入汇总、不附原件'
        self.lbl_sum.configure(text=txt)

    def _browse(self) -> None:
        p = filedialog.askdirectory(title="选择保存目录", initialdir=self.dir_var.get() or None,
                                    parent=self)
        if p:
            self.dir_var.set(os.path.normpath(p))

    def _go(self) -> None:
        if not self.summary_rows:
            self.lbl_msg.configure(text="所选范围内没有发票。")
            return
        d = self.dir_var.get().strip().strip('"')
        if not d:
            self.lbl_msg.configure(text="请填写或选择保存文件夹。")
            return
        d = os.path.expanduser(os.path.expandvars(d))
        if not os.path.isdir(d):
            try:
                os.makedirs(d)
            except OSError as exc:
                self.lbl_msg.configure(text=f"无法创建文件夹：{exc}")
                return
        name = self.name_var.get().strip()
        if not name:
            self.lbl_msg.configure(text="请填写文件名。")
            return
        if set(name) & self.BAD_CHARS:
            self.lbl_msg.configure(text="文件名不能包含 \\ / : * ? \" < > |")
            return
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        target = os.path.join(d, name)
        if os.path.exists(target) and not messagebox.askyesno(
                "文件已存在", f"同名文件已存在：\n{target}\n\n要覆盖它吗？", parent=self):
            return
        self.app.cfg["export_dir"] = d
        try:
            core.save_config(self.app.cfg)
        except OSError:
            pass
        rows = list(self.summary_rows)
        title = (self.title_var.get().strip() or "费用报销单")[:40]
        note = self.note_var.get().strip()[:70]
        self.destroy()
        self.app._export_reimbursement_to(target, rows, title, note)


class SettingsDialog(tk.Toplevel):
    def __init__(self, app: FileKeeperApp, cfg: Dict[str, Any], on_saved: Callable):
        super().__init__(app.root)
        self.app = app
        self.cfg = cfg
        self.on_saved = on_saved
        self.title("设置")
        self.geometry("560x500")
        self.configure(bg=CARD)
        self.transient(app.root)
        self.grab_set()

        pad = tk.Frame(self, bg=CARD)
        pad.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(pad, text="归档根目录", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        row = tk.Frame(pad, bg=CARD)
        row.pack(fill="x", pady=(4, 14))
        self.root_var = tk.StringVar(value=cfg.get("archive_root", core.default_root()))
        self.root_entry = ttk.Entry(row, textvariable=self.root_var)
        app._button(row, "浏览", self._browse, "secondary", font_size=9).pack(side="right")
        self.root_entry.pack(side="left", fill="x", expand=True)

        tk.Label(pad, text="归档动作", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.action = tk.StringVar(value=cfg.get("action", "copy"))
        act = tk.Frame(pad, bg=CARD)
        act.pack(fill="x", pady=(4, 14))
        for text, val in (("复制（原文件保留，推荐）", "copy"), ("移动", "move")):
            tk.Radiobutton(act, text=text, variable=self.action, value=val,
                           bg=CARD, activebackground=CARD, selectcolor="#FFFFFF",
                           font=(FONT, 9), bd=0, highlightthickness=0,
                           cursor="hand2").pack(side="left", padx=(0, 12))

        self.prefix = tk.BooleanVar(value=bool(cfg.get("date_prefix")))
        tk.Checkbutton(pad, text="归档时给文件名加日期前缀（20261121_）", variable=self.prefix,
                       bg=CARD, activebackground=CARD, selectcolor="#FFFFFF",
                       font=(FONT, 9), bd=0, highlightthickness=0,
                       cursor="hand2").pack(anchor="w", pady=(0, 4))
        self.open_after = tk.BooleanVar(value=bool(cfg.get("open_after_archive")))
        tk.Checkbutton(pad, text="归档完成后自动打开所在文件夹", variable=self.open_after,
                       bg=CARD, activebackground=CARD, selectcolor="#FFFFFF",
                       font=(FONT, 9), bd=0, highlightthickness=0,
                       cursor="hand2").pack(anchor="w", pady=(0, 4))
        self.month = tk.BooleanVar(value=bool(cfg.get("month_folder")))
        tk.Checkbutton(pad, text="分类下再按年月分子目录（06_报告与总结/2026-11）", variable=self.month,
                       bg=CARD, activebackground=CARD, selectcolor="#FFFFFF",
                       font=(FONT, 9), bd=0, highlightthickness=0,
                       cursor="hand2").pack(anchor="w", pady=(0, 4))
        self.ocr = tk.BooleanVar(value=bool(cfg.get("ocr", True)))
        tk.Checkbutton(pad, text="扫描件/图片用 Windows OCR 识别文字（发票、截图）", variable=self.ocr,
                       bg=CARD, activebackground=CARD, selectcolor="#FFFFFF",
                       font=(FONT, 9), bd=0, highlightthickness=0,
                       cursor="hand2").pack(anchor="w", pady=(0, 4))

        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=12)
        tk.Label(pad, text="品牌 Logo", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        self.logo_action = "keep"
        self.logo_file = ""
        logo_row = tk.Frame(pad, bg=CARD)
        logo_row.pack(fill="x", pady=(4, 4))
        self.logo_preview = tk.Label(logo_row, bg=SOFT_GREY, padx=12, pady=8,
                                     highlightthickness=1, highlightbackground=BORDER)
        self.logo_preview.pack(side="left")
        logo_btns = tk.Frame(logo_row, bg=CARD)
        logo_btns.pack(side="left", padx=(12, 0))
        app._button(logo_btns, "选择图片", self._pick_logo, "secondary", font_size=9).pack(anchor="w")
        app._button(logo_btns, "恢复默认", self._reset_logo, "ghost", font_size=9).pack(anchor="w", pady=(6, 0))
        self.logo_hint = tk.Label(pad, text="支持 PNG / JPG / WEBP，透明背景效果更好；本机选择优先于后台品牌图，保存后立即生效。",
                                  bg=CARD, fg=MUTED, font=(FONT, 8))
        self.logo_hint.pack(anchor="w")
        self._refresh_logo_preview()

        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=12)
        tk.Label(pad, text="数据位置", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
        tk.Label(pad, text=core.APP_DIR, bg=CARD, fg="#334155", font=(FONT, 9),
                 wraplength=500, justify="left").pack(anchor="w", pady=(4, 2))
        tk.Label(pad, text="记录保存在本地 SQLite，不上传任何地方。", bg=CARD, fg=MUTED,
                 font=(FONT, 8)).pack(anchor="w")

        foot = tk.Frame(pad, bg=CARD)
        foot.pack(fill="x", side="bottom", pady=(16, 0))
        app._button(foot, "保存设置", self._save, "primary").pack(side="right")
        app._button(foot, "取消", self.destroy, "ghost").pack(side="right", padx=(0, 8))

        self.update_idletasks()
        w = 640
        h = min(self.winfo_screenheight() - 80, max(self.winfo_reqheight() + 8, 540))
        x = app.root.winfo_rootx() + (app.root.winfo_width() - w) // 2
        y = app.root.winfo_rooty() + max(30, (app.root.winfo_height() - h) // 2)
        self.geometry(f"{w}x{h}+{max(x, 10)}+{max(y, 10)}")

    def _logo_view_source(self) -> str:
        if self.logo_action == "set" and self.logo_file and os.path.isfile(self.logo_file):
            return self.logo_file
        if self.logo_action != "reset" and os.path.isfile(core.LOGO_PATH):
            return core.LOGO_PATH
        remote = os.path.join(core.APP_DIR, "brand_logo.png")
        if os.path.isfile(remote):
            return remote
        return _asset_path("logo.png")

    def _refresh_logo_preview(self) -> None:
        photo = self.app._logo_photo(self._logo_view_source(), 44)
        if photo:
            self._preview_photo = photo
            self.logo_preview.configure(image=photo, text="", padx=12, pady=8)
        else:
            self._preview_photo = None
            self.logo_preview.configure(image="", text=core.APP_NAME, padx=18, pady=16,
                                        fg=ACCENT, font=(FONT, 14, "bold"))

    def _pick_logo(self) -> None:
        p = filedialog.askopenfilename(
            title="选择 Logo 图片", parent=self,
            filetypes=[("图片", "*.png *.jpg *.jpeg *.webp *.bmp"), ("所有文件", "*.*")])
        if not p:
            return
        self.logo_action = "set"
        self.logo_file = p
        self.logo_hint.configure(text=f"已选择：{os.path.basename(p)}；保存后生效。", fg="#334155")
        self._refresh_logo_preview()

    def _reset_logo(self) -> None:
        self.logo_action = "reset"
        self.logo_file = ""
        self.logo_hint.configure(text="已恢复默认 Logo；保存后生效。", fg="#334155")
        self._refresh_logo_preview()

    def _save_logo_change(self) -> bool:
        if self.logo_action == "set":
            if not os.path.isfile(self.logo_file):
                messagebox.showwarning("Logo 文件不存在", "选择的 Logo 图片已经找不到，请重新选择。", parent=self)
                return False
            try:
                core.ensure_app_dir()
                shutil.copyfile(self.logo_file, core.LOGO_PATH)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Logo 保存失败", f"无法保存 Logo：{exc}", parent=self)
                return False
        elif self.logo_action == "reset":
            try:
                if os.path.isfile(core.LOGO_PATH):
                    os.remove(core.LOGO_PATH)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Logo 恢复失败", f"无法恢复默认 Logo：{exc}", parent=self)
                return False
        return True

    def _browse(self) -> None:
        p = filedialog.askdirectory(title="选择归档根目录", initialdir=self.root_var.get() or None)
        if p:
            self.root_var.set(os.path.normpath(p))

    def _save(self) -> None:
        root = os.path.expanduser(os.path.expandvars(self.root_var.get().strip())) or core.default_root()
        if os.path.exists(root) and not os.path.isdir(root):
            messagebox.showwarning("路径不可用", f"归档根目录必须是一个文件夹，而不是文件：\n{root}", parent=self)
            return
        if not os.path.isdir(root):
            try:
                os.makedirs(root)
            except OSError as exc:
                messagebox.showwarning("无法创建目录", f"无法创建归档根目录：\n{root}\n{exc}", parent=self)
                return
        if not os.access(root, os.W_OK):
            messagebox.showwarning("没有写入权限", f"当前账号无法写入这个目录：\n{root}", parent=self)
            return
        self.cfg["archive_root"] = root
        self.cfg["action"] = self.action.get()
        self.cfg["date_prefix"] = bool(self.prefix.get())
        self.cfg["open_after_archive"] = bool(self.open_after.get())
        self.cfg["month_folder"] = bool(self.month.get())
        self.cfg["ocr"] = bool(self.ocr.get())
        if not self._save_logo_change():
            return
        try:
            core.save_config(self.cfg)
        except OSError as exc:
            messagebox.showerror("保存失败", f"设置没有保存成功：{exc}", parent=self)
            return
        self.on_saved()
        self.destroy()


class BatchDialog(tk.Toplevel):
    def __init__(self, app: FileKeeperApp, analyses: List[Dict[str, Any]]):
        super().__init__(app.root)
        self.app = app
        self.items = [dict(a) for a in analyses]
        for a in self.items:
            a["_suggest"] = a["category"]
        self.title(f"批量归档 · {len(self.items)} 个文件")
        self.geometry("1280x720")
        self.configure(bg=CARD)
        self.transient(app.root)
        self.grab_set()

        pad = tk.Frame(self, bg=CARD)
        pad.pack(fill="both", expand=True, padx=18, pady=14)
        app._section_title(pad, "确认批量归档",
                           "支持多选批量改分类 / 改识别信息 / 重新识别").pack(anchor="w")

        bar = tk.Frame(pad, bg=CARD)
        bar.pack(fill="x", pady=(8, 6))
        app._button(bar, "全选", self._select_all, "ghost").pack(side="left")
        app._button(bar, "批量改分类", self._bulk_category, "secondary").pack(side="left", padx=(8, 0))
        app._button(bar, "批量改识别信息", self._bulk_edit, "secondary").pack(side="left", padx=(8, 0))
        app._button(bar, "重新识别", self._reidentify, "secondary").pack(side="left", padx=(8, 0))
        app._label(bar, "提示：Ctrl/Shift 多选；双击某行也可单独修改", 9, MUTED).pack(side="left", padx=(12, 0))

        wrap = tk.Frame(pad, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        wrap.pack(fill="both", expand=True, pady=(0, 8))
        cols = ("name", "title", "cat", "inv", "conf", "size")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="extended")
        for c, t, w, a in zip(cols, ("文件名", "识别标题", "分类", "发票识别", "置信度", "大小"),
                              (360, 290, 150, 240, 70, 90), ("w", "w", "w", "w", "e", "e")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=a, stretch=False)
        self.tree.tag_configure("dup", background="#FFF7ED", foreground="#B45309")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.tree.configure(yscrollcommand=sb.set, xscrollcommand=hsb.set)
        self.tree.bind("<Double-1>", self._edit_row)
        self.tree.bind("<Control-a>", lambda e: (self._select_all(), "break")[1])
        self._render()

        opt = tk.Frame(pad, bg=CARD)
        opt.pack(fill="x")
        self.summary = tk.BooleanVar(value=True)
        tk.Checkbutton(opt, text="发票按汇总建子文件夹", variable=self.summary,
                       command=self._update_summary, bg=CARD, activebackground=CARD,
                       selectcolor="#FFFFFF", font=(FONT, 9), bd=0,
                       highlightthickness=0).pack(side="left")
        self.lbl_sum = app._label(opt, "", 9, MUTED)
        self.lbl_sum.pack(side="left", padx=(8, 0))

        foot = tk.Frame(pad, bg=CARD)
        foot.pack(fill="x", pady=(8, 0))
        self.lbl = app._label(foot, f"共 {len(self.items)} 个文件", 9, MUTED)
        self.lbl.pack(side="left")
        app._button(foot, "取消", self.destroy, "ghost").pack(side="right")
        app._button(foot, "全部归档", self._archive_all, "primary").pack(side="right", padx=(0, 8))
        app._button(foot, "全部放入待分类", self._all_pending, "secondary").pack(side="right", padx=(0, 8))
        self._update_summary()

    # ---- helpers
    def _selected(self) -> List[int]:
        return sorted(int(i) for i in self.tree.selection())

    def _select_all(self) -> None:
        self.tree.selection_set(self.tree.get_children())

    def _inv_items(self) -> List[Dict[str, Any]]:
        inv_cat = next((f["name"] for f in self.app.current.get("folders", [])
                        if invoice_mod.is_invoice_folder(f["name"])), "")
        return [a for a in self.items
                if _is_invoice_analysis(a) and (not inv_cat or a["category"] == inv_cat)]

    def _summary_name(self) -> str:
        if not self.summary.get():
            return ""
        return invoice_mod.batch_folder_name([a["invoice"] for a in self._inv_items()])

    def _update_summary(self) -> None:
        name = self._summary_name()
        invs = self._inv_items()
        total = sum(float((a.get("invoice") or {}).get("amount") or 0) for a in invs)
        if name:
            self.lbl_sum.configure(text=f"子文件夹：{name}（{len(invs)} 张 · ¥{total:.2f}）", fg=OK)
        else:
            self.lbl_sum.configure(text="未启用（文件直接放入发票目录）"
                                   if not self.summary.get() else "没有已识别的发票，暂不建子文件夹",
                                   fg=MUTED)

    def _render(self) -> None:
        sel = self.tree.selection()
        for i in self.tree.get_children():
            self.tree.delete(i)
        for idx, a in enumerate(self.items):
            inv = a.get("invoice") or {}
            inv_txt = ""
            if inv:
                mark = "✓" if inv.get("verified") else "⚠"
                date_txt = (inv.get("date") or "")[5:10]
                inv_txt = f'{mark} {date_txt} {inv.get("category", "")} ¥{float(inv.get("amount") or 0):.2f}'
                if a.get("invoice_duplicate"):
                    inv_txt += " 重复"
            elif a.get("invoice_unparsed"):
                inv_txt = "疑似发票 · 未识别"
            tags = ("dup",) if a.get("invoice_duplicate") else ()
            self.tree.insert("", "end", iid=str(idx), tags=tags,
                             values=(a["name"], a["title"], a["category"], inv_txt,
                                     f'{int(a.get("confidence", 0) * 100)}%',
                                     core.human_size(a["size"])))
        if sel:
            self.tree.selection_set(sel)
        if hasattr(self, "summary"):
            self._update_summary()

    def _apply_invoice(self, idxs: List[int], fields: Dict[str, Any]) -> None:
        cat_inv = next((f["name"] for f in self.app.current.get("folders", [])
                        if invoice_mod.is_invoice_folder(f["name"])), "")
        for i in idxs:
            a = self.items[i]
            inv = dict(a.get("invoice") or {})
            for k, v in fields.items():
                if v not in (None, ""):
                    inv[k] = v
            if not inv:
                continue
            if "amount" in inv:
                try:
                    inv["amount"] = float(inv["amount"])
                except (TypeError, ValueError):
                    inv.pop("amount", None)
            a["invoice"] = inv
            inv["verified"] = True          # 人工修改即视为已确认
            inv["verify_issues"] = []
            a["invoice_unparsed"] = False
            a["invoice_duplicate"] = False
            a["confidence"] = max(float(a.get("confidence") or 0), 0.92)
            if cat_inv and not invoice_mod.is_invoice_folder(a["category"]):
                a["category"] = cat_inv
            a["suggest_name"] = invoice_mod.suggest_name(inv, "") + a.get("ext", "").lower()
        self._render()

    # ---- actions
    def _bulk_category(self) -> None:
        idxs = self._selected()
        if not idxs:
            messagebox.showinfo("批量改分类", "请先在列表里选中要修改的行（可 Ctrl/Shift 多选）。", parent=self)
            return
        cat = _choose_category(self, self.app.current, self.items[idxs[0]]["category"])
        if cat:
            for i in idxs:
                self.items[i]["category"] = cat
            self._render()
            self.lbl.configure(text=f"已把 {len(idxs)} 个文件改为 {cat}", fg=WARN)

    def _bulk_edit(self) -> None:
        idxs = self._selected()
        if not idxs:
            messagebox.showinfo("批量改识别信息", "请先选中要修改的行。", parent=self)
            return
        BatchInfoDialog(self, len(idxs), lambda f: self._apply_invoice(idxs, f))

    def _reidentify(self) -> None:
        idxs = self._selected() or list(range(len(self.items)))
        self.configure(cursor="watch")
        self.update_idletasks()
        failed = 0
        for i in idxs:
            a = self.items[i]
            try:
                new = core.analyze_file(a["path"], self.app.current, check_duplicate=False)
                new["_suggest"] = new["category"]
                self.items[i] = new
            except Exception:
                failed += 1
        self.configure(cursor="")
        self.lbl.configure(text=f"已重新识别 {len(idxs) - failed} 个"
                                + (f"（{failed} 个失败）" if failed else ""), fg=OK)
        self._render()

    def _edit_row(self, event) -> None:
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        a = self.items[int(iid)]
        self.tree.selection_set(iid)
        BatchInfoDialog(self, 1, lambda f: self._apply_invoice([int(iid)], f))

    def _all_pending(self) -> None:
        fb = core.fallback_folder(self.app.current)
        for a in self.items:
            a["category"] = fb
        self._render()
        self.lbl.configure(text=f"已全部改为 {fb}", fg=WARN)

    def _archive_all(self) -> None:
        subfolder = self._summary_name() if self.summary.get() else ""
        items = [(a, a["category"], a["title"]) for a in self.items]
        self.destroy()
        self.app._archive_many(items, refresh_detail=False, subfolder=subfolder)


class BatchInfoDialog(tk.Toplevel):
    """批量修改识别信息：留空表示不修改。"""
    CATS = ("住宿", "餐饮", "交通", "话费", "办公", "差旅", "其他")

    def __init__(self, master, count: int, on_apply: Callable[[Dict[str, Any]], None]):
        super().__init__(master)
        self.title(f"批量修改识别信息 · {count} 项")
        self.configure(bg=CARD)
        self.transient(master)
        self.grab_set()
        pad = tk.Frame(self, bg=CARD)
        pad.pack(fill="both", expand=True, padx=24, pady=18)
        tk.Label(pad, text="只填需要修改的项，留空表示保持原值；日期格式 YYYY-MM-DD",
                 bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(0, 6))
        self.vars: Dict[str, tk.StringVar] = {}

        def field(key, label):
            tk.Label(pad, text=label, bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(6, 0))
            var = tk.StringVar()
            if key == "category":
                ttk.Combobox(pad, textvariable=var, values=self.CATS, state="readonly").pack(fill="x", pady=(4, 0))
            else:
                ttk.Entry(pad, textvariable=var).pack(fill="x", pady=(4, 0))
            self.vars[key] = var

        field("date", "开票日期")
        field("category", "类别")
        field("seller", "销售方")
        field("amount", "金额（元）")
        field("invoice_no", "发票号码")
        foot = tk.Frame(pad, bg=CARD)
        foot.pack(fill="x", pady=(14, 0))

        def apply():
            data = {k: v.get().strip() for k, v in self.vars.items()}
            data = {k: v for k, v in data.items() if v}
            if "amount" in data:
                try:
                    data["amount"] = float(data["amount"])
                except ValueError:
                    messagebox.showwarning("金额格式", "金额需为数字，如 88.00", parent=self)
                    return
            if data.get("date") and len(data["date"]) == 10 and data["date"][4] == "-":
                pass
            self.destroy()
            on_apply(data)

        tk.Button(foot, text="应用", command=apply, bg=ACCENT, fg="#FFFFFF",
                  relief="flat", font=(FONT, 10, "bold"), padx=18, pady=6,
                  cursor="hand2").pack(side="right")
        tk.Button(foot, text="取消", command=self.destroy, bg=CARD, fg=MUTED,
                  relief="flat", font=(FONT, 10), padx=14, pady=6,
                  cursor="hand2").pack(side="right", padx=(0, 8))
        self.resizable(False, False)


class InvoiceEditDialog(tk.Toplevel):
    CATS = ("住宿", "餐饮", "交通", "话费", "办公", "差旅", "其他")

    def __init__(self, app: FileKeeperApp, row, on_saved: Callable[[], None]):
        super().__init__(app.root)
        self.app, self.row, self.on_saved = app, row, on_saved
        self.title("修改发票信息")
        self.configure(bg=CARD)
        self.transient(app.root)
        self.grab_set()
        pad = tk.Frame(self, bg=CARD)
        pad.pack(fill="both", expand=True, padx=24, pady=18)

        def field(label, value, width=None):
            tk.Label(pad, text=label, bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(6, 0))
            var = tk.StringVar(value=str(value or ""))
            (ttk.Combobox(pad, textvariable=var, values=self.CATS, state="readonly")
             if label == "类别" else ttk.Entry(pad, textvariable=var)).pack(fill="x", pady=(4, 0))
            return var

        self.v_date = field("开票日期（YYYY-MM-DD）", row["inv_date"])
        self.v_cat = field("类别", row["category"])
        self.v_seller = field("销售方", row["seller"])
        self.v_amount = field("金额（元）", f'{float(row["amount"] or 0):.2f}' if row["amount"] else "")
        self.v_no = field("发票号码", row["invoice_no"])
        self.v_note = field("备注", row["note"])
        self.rename = tk.BooleanVar(value=True)
        tk.Checkbutton(pad, text="按新信息同步重命名文件", variable=self.rename,
                       bg=CARD, activebackground=CARD, selectcolor="#FFFFFF",
                       font=(FONT, 9), bd=0, highlightthickness=0).pack(anchor="w", pady=(10, 0))
        foot = tk.Frame(pad, bg=CARD)
        foot.pack(fill="x", pady=(14, 0))
        app._button(foot, "保存", self._save, "primary").pack(side="right")
        app._button(foot, "取消", self.destroy, "ghost").pack(side="right", padx=(0, 8))
        self.update_idletasks()
        w, h = 480, max(self.winfo_reqheight() + 20, 420)
        self.geometry(f"{w}x{h}+{app.root.winfo_rootx() + 300}+{app.root.winfo_rooty() + 120}")

    def _save(self) -> None:
        try:
            amount = float(self.v_amount.get().replace("¥", "").strip() or 0)
        except ValueError:
            amount = 0
        fields = {
            "inv_date": self.v_date.get().strip(),
            "category": self.v_cat.get().strip(),
            "seller": self.v_seller.get().strip(),
            "amount": amount,
            "invoice_no": self.v_no.get().strip(),
            "note": self.v_note.get().strip(),
        }
        core.update_invoice(self.row["id"], **fields)
        if self.rename.get() and self.row["record_id"]:
            from . import invoice as _inv
            new_name = _inv.suggest_name({
                "date": fields["inv_date"], "category": fields["category"],
                "seller": fields["seller"], "amount": amount,
                "invoice_no": fields["invoice_no"]}) + os.path.splitext(self.row["file_path"] or "")[1]
            if new_name.strip("_") and core.rename_record_to(self.row["record_id"], new_name):
                pass
        self.on_saved()
        self.destroy()


class ManualInvoiceDialog(tk.Toplevel):
    """给「疑似发票 · 未识别」的归档记录手工补录台账。"""

    CATS = ("住宿", "餐饮", "交通", "话费", "办公", "差旅", "其他")

    def __init__(self, app: FileKeeperApp, rec, on_saved: Callable[[], None]):
        super().__init__(app.root)
        self.app, self.rec, self.on_saved = app, rec, on_saved
        self.title("补录发票台账")
        self.configure(bg=CARD)
        self.transient(app.root)
        self.grab_set()
        from . import invoice as _inv
        base = os.path.basename(rec["dst_path"] or rec["name"] or "")
        d_date = _inv._date_from_name(base) or (rec["archived_at"] or "")[:10]
        d_amount = _inv._amount_from_name(base) or ""
        d_seller = _inv._seller_from_name(base) or ""
        d_cat = _inv.detect_category("", base)

        pad = tk.Frame(self, bg=CARD)
        pad.pack(fill="both", expand=True, padx=24, pady=16)
        tk.Label(pad, text=f"文件：{base}", bg=CARD, fg=MUTED, font=(FONT, 9),
                 wraplength=430, justify="left").pack(anchor="w")
        tk.Label(pad, text="识别不出的扫描件，可按票面手工填写；保存后进入发票台账。",
                 bg=SOFT_BLUE, fg=ACCENT, font=(FONT, 9), anchor="w", justify="left",
                 wraplength=440, padx=8, pady=5).pack(fill="x", pady=(8, 4))

        def field(label, value):
            tk.Label(pad, text=label, bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(6, 0))
            var = tk.StringVar(value=str(value or ""))
            (ttk.Combobox(pad, textvariable=var, values=self.CATS, state="readonly")
             if label == "类别" else ttk.Entry(pad, textvariable=var)).pack(fill="x", pady=(3, 0))
            return var

        self.v_date = field("开票日期（YYYY-MM-DD）", d_date)
        self.v_cat = field("类别", d_cat if d_cat in self.CATS else "其他")
        self.v_seller = field("销售方（开票公司）", d_seller)
        self.v_amount = field("金额（元）", f"{d_amount:.2f}" if d_amount else "")
        self.v_no = field("发票号码（可空）", "")
        self.v_note = field("备注", "手工补录")

        self.rename = tk.BooleanVar(value=True)
        tk.Checkbutton(pad, text="按补录信息重命名文件（日期_类别_销售方_金额）", variable=self.rename,
                       bg=CARD, activebackground=CARD, selectcolor="#FFFFFF",
                       font=(FONT, 9), bd=0, highlightthickness=0).pack(anchor="w", pady=(10, 0))
        foot = tk.Frame(pad, bg=CARD)
        foot.pack(fill="x", pady=(12, 0))
        app._button(foot, "保存并记账", self._save, "primary").pack(side="right")
        app._button(foot, "取消", self.destroy, "ghost").pack(side="right", padx=(0, 8))
        self.update_idletasks()
        w, h = 500, max(self.winfo_reqheight() + 16, 470)
        self.geometry(f"{w}x{h}+{app.root.winfo_rootx() + 280}+{app.root.winfo_rooty() + 100}")

    def _save(self) -> None:
        date = self.v_date.get().strip()
        cat = self.v_cat.get().strip() or "其他"
        seller = self.v_seller.get().strip()
        try:
            amount = float(self.v_amount.get().replace("¥", "").replace(",", "").strip() or 0)
        except ValueError:
            messagebox.showwarning("金额格式不对", "金额只能是数字，例如 128.50")
            return
        if not date and not amount:
            if not messagebox.askyesno("信息太少", "日期和金额都没填，仍要记账吗？"):
                return
        fields = {"inv_date": date, "category": cat, "seller": seller, "amount": amount,
                  "invoice_no": self.v_no.get().strip(), "note": self.v_note.get().strip()}
        try:
            core.create_invoice_for_record(self.rec["id"], fields)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("补录失败", str(exc))
            return
        if self.rename.get():
            from . import invoice as _inv
            ext = os.path.splitext(self.rec["dst_path"] or "")[1]
            new_name = _inv.suggest_name({"date": date, "category": cat, "seller": seller,
                                          "amount": amount}) + ext
            if new_name.strip("_") and core.rename_record_to(self.rec["id"], new_name):
                pass
        self.on_saved()
        self.destroy()


class BatchRenameDialog(tk.Toplevel):
    PATTERNS = ["{date}_{category}_{name}", "{date}_{name}", "{category}_{i}_{name}",
                "{date}_{category}_{title}", "发票_{date}_{seller}_{amount}", "{name}_{date}"]

    def __init__(self, app: FileKeeperApp, rows: List[Dict[str, Any]], selected: bool):
        super().__init__(app.root)
        self.app = app
        self.rows = rows
        # 记录表本身不含发票字段；批量重命名的 {seller}/{amount} 需要从台账补齐
        try:
            with core._conn() as con:
                for r in self.rows:
                    rid = r.get("record_id") or r.get("id")
                    if not rid:
                        continue
                    inv = con.execute("SELECT seller,amount FROM invoices WHERE record_id=? LIMIT 1",
                                      (rid,)).fetchone()
                    if inv:
                        r.setdefault("seller", inv["seller"] or "")
                        r.setdefault("amount", f"{float(inv['amount'] or 0):.2f}" if inv["amount"] else "")
        except Exception:
            pass
        self.title(f"批量重命名 · {len(rows)} 个文件")
        self.configure(bg=CARD)
        self.transient(app.root)
        self.grab_set()
        self.geometry("1100x620")
        pad = tk.Frame(self, bg=CARD)
        pad.pack(fill="both", expand=True, padx=18, pady=14)
        app._section_title(pad, "批量重命名", "先预览再执行；执行后可「撤销上一步」整体还原").pack(anchor="w")
        tk.Label(pad, text="范围：" + ("选中的记录" if selected else "全部记录"),
                 bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(6, 0))

        tk.Label(pad, text="命名规则（可点选预设，也可自己改；{ext} 会自动补）",
                 bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(8, 0))
        self.pattern = tk.StringVar(value=self.PATTERNS[0])
        box = ttk.Combobox(pad, textvariable=self.pattern, values=self.PATTERNS)
        box.pack(fill="x", pady=(4, 6))
        box.bind("<<ComboboxSelected>>", lambda _e: self._preview())
        self.pattern.trace_add("write", lambda *_: self._preview())
        tk.Label(pad, text="可用：{date} {year} {month} {category} {title} {name} {i} {seller} {amount}",
                 bg=CARD, fg=MUTED, font=(FONT, 8)).pack(anchor="w")

        wrap = tk.Frame(pad, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        wrap.pack(fill="both", expand=True, pady=(8, 8))
        cols = ("old", "new", "state")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, t, w in zip(cols, ("原文件名", "新文件名", "状态"), (320, 660, 90)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.tree.configure(yscrollcommand=sb.set, xscrollcommand=hsb.set)

        foot = tk.Frame(pad, bg=CARD)
        foot.pack(fill="x")
        self.lbl = app._label(foot, "", 9, MUTED)
        self.lbl.pack(side="left")
        app._button(foot, "执行重命名", self._apply, "primary").pack(side="right")
        app._button(foot, "取消", self.destroy, "ghost").pack(side="right", padx=(0, 8))
        self._preview()

    def _preview(self) -> None:
        plan = core.plan_rename(self.rows, self.pattern.get(), 1)
        for i in self.tree.get_children():
            self.tree.delete(i)
        for p in plan:
            state = "冲突：重名" if p["conflict"] else ("不变" if p["old_name"] == p["new_name"] else "可改")
            self.tree.insert("", "end", values=(p["old_name"], p["new_name"], state))
        ok = sum(1 for p in plan if not p["conflict"] and p["old_name"] != p["new_name"])
        self.lbl.configure(text=f"共 {len(plan)} 个，可改 {ok} 个")

    def _apply(self) -> None:
        plan = core.plan_rename(self.rows, self.pattern.get(), 1)
        if not messagebox.askyesno("确认重命名", f"将重命名 {len(plan)} 个文件，可在「撤销上一步」还原。确定执行？"):
            return
        res = core.apply_rename(plan)
        self.destroy()
        self.app._refresh_records()
        self.app._refresh_recent()
        msg = f"已重命名 {len(res['done'])} 个文件"
        if res["failed"]:
            msg += f"，失败 {len(res['failed'])} 个：\n" + "\n".join(res["failed"][:6])
        self.app._set_status(msg.splitlines()[0], OK if not res["failed"] else WARN)
        messagebox.showinfo("批量重命名结果", msg)


class UndoHistoryDialog(tk.Toplevel):
    def __init__(self, app: FileKeeperApp, on_undo: Callable[[], None]):
        super().__init__(app.root)
        self.app, self.on_undo = app, on_undo
        self.title("操作历史 / 撤销")
        self.configure(bg=CARD)
        self.transient(app.root)
        self.grab_set()
        self.geometry("1080x500")
        pad = tk.Frame(self, bg=CARD)
        pad.pack(fill="both", expand=True, padx=18, pady=14)
        app._section_title(pad, "操作历史", "归档与重命名都可撤销，从最近一步开始").pack(anchor="w")
        wrap = tk.Frame(pad, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        wrap.pack(fill="both", expand=True, pady=(8, 8))
        cols = ("ts", "kind", "detail", "state")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, t, w in zip(cols, ("时间", "类型", "内容", "状态"), (210, 70, 650, 90)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.tree.configure(yscrollcommand=sb.set, xscrollcommand=hsb.set)
        foot = tk.Frame(pad, bg=CARD)
        foot.pack(fill="x")
        app._button(foot, "撤销最近一步", self._undo, "primary").pack(side="right")
        app._button(foot, "关闭", self.destroy, "ghost").pack(side="right", padx=(0, 8))
        self._load()

    def _load(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in core.undo_history(40):
            kind = "归档" if r["kind"] == "archive" else "重命名"
            payload = {}
            try:
                import json as _json
                payload = _json.loads(r["payload"] or "{}")
            except Exception:
                pass
            detail = ""
            if r["kind"] == "archive":
                detail = payload.get("dst", "").split("\\")[-1]
            else:
                detail = f'{len(payload.get("items", []))} 个文件'
            self.tree.insert("", "end", values=(r["ts"], kind, detail,
                                               "已撤销" if r["undone"] else "可撤销"))

    def _undo(self) -> None:
        self.on_undo()
        self._load()


class _CategoryPicker(tk.Toplevel):
    def __init__(self, master, preset, current):
        super().__init__(master)
        self.result: Optional[str] = None
        self.title("选择分类")
        self.geometry("360x120")
        self.configure(bg=CARD)
        self.transient(master)
        self.grab_set()
        pad = tk.Frame(self, bg=CARD)
        pad.pack(fill="both", expand=True, padx=16, pady=14)
        self.var = tk.StringVar(value=current)
        box = ttk.Combobox(pad, textvariable=self.var, state="readonly",
                           values=[f["name"] for f in preset["folders"]])
        box.pack(fill="x")
        box.focus_set()
        foot = tk.Frame(pad, bg=CARD)
        foot.pack(fill="x", pady=(10, 0))
        tk.Button(foot, text="确定", command=self._ok, bg=ACCENT, fg="#fff", bd=0,
                  font=(FONT, 9), padx=14, pady=4, cursor="hand2").pack(side="right")
        box.bind("<<ComboboxSelected>>", lambda _e: self._ok())
        self.wait_window(self)

    def _ok(self) -> None:
        self.result = self.var.get()
        self.destroy()


def _choose_category(master, preset, current) -> Optional[str]:
    return _CategoryPicker(master, preset, current).result




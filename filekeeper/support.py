# -*- coding: utf-8 -*-
"""在线客服：注册/续费窗口内的会话窗口，消息走注册后台。"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
import urllib.error
from tkinter import ttk

from . import core
from . import license as lic

FONT = "微软雅黑"
BG = "#F4F6FB"
CARD = "#FFFFFF"
ACCENT = "#2563EB"
TEXT = "#111827"
MUTED = "#6B7280"
BORDER = "#E3E8F0"
OK = "#15803D"
DANGER = "#DC2626"
SOFT_BLUE = "#EEF4FF"
SOFT_GREEN = "#ECFDF5"
POLL_MS = 3000


def _err_text(exc: Exception) -> str:
    """把服务端 JSON 错误转成可读提示（429/400 的 body 里带 error）。"""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            raw = exc.read().decode("utf-8", "replace")
            import json
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("error"):
                return str(data["error"])
        except Exception:
            pass
        return f"服务端返回 {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return "网络连接失败，请检查网络后重试"
    return str(exc) or exc.__class__.__name__


class SupportChatDialog(tk.Toplevel):
    def __init__(self, parent, version: str = "", on_close=None):
        super().__init__(parent)
        self.version = version
        self.on_close = on_close
        self._closed = False
        self._in_flight = False
        self._sending = False
        self._last_id = 0
        self._last_status = ""
        self._poll_job = None
        self._drain_job = None
        self._results: queue.Queue = queue.Queue()
        self._seen: set[int] = set()
        self.title(f"{core.APP_NAME} · 在线客服")
        self.configure(bg=BG)
        self.transient(parent)
        self.resizable(False, False)
        self._build()
        self._center(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._drain_job = self.after(120, self._drain)
        self._tick()          # 打开即拉一次历史消息

    # ------------------------------------------------------------ UI
    def _center(self, parent) -> None:
        self.update_idletasks()
        w, h = 540, 660
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - w) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self) -> None:
        head = tk.Frame(self, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        head.pack(fill="x")
        tk.Label(head, text="在线客服", bg=CARD, fg=ACCENT, font=(FONT, 14, "bold")).pack(
            side="left", padx=18, pady=(12, 2))
        tk.Label(head, text="工作日 9:00-18:00 在线，留言会尽快回复", bg=CARD, fg=MUTED,
                 font=(FONT, 8)).pack(side="left", padx=(0, 10), pady=(16, 2))
        self.btn_close = tk.Label(head, text="关闭", bg=CARD, fg=TEXT, font=(FONT, 9), padx=10,
                                 pady=4, cursor="hand2", highlightthickness=1,
                                 highlightbackground=BORDER)
        self.btn_close.pack(side="right", padx=14, pady=10)
        self.btn_close.bind("<Button-1>", lambda _e: self._close())

        who = tk.Frame(self, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        who.pack(fill="x", pady=(8, 0), padx=12)
        ev = lic.evaluate()
        code = ev.get("code") or "未生成（发送时自动联网注册）"
        self.lbl_machine = tk.Label(who, text=f"机器码：{ev.get('machine', '')}", bg=CARD, fg=MUTED,
                                    font=(FONT, 8))
        self.lbl_machine.pack(anchor="w", padx=14, pady=(8, 1))
        self.lbl_code = tk.Label(who, text=f"注册码：{code}", bg=CARD, fg=MUTED, font=(FONT, 8))
        self.lbl_code.pack(anchor="w", padx=14, pady=(0, 8))

        chat_wrap = tk.Frame(self, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        chat_wrap.pack(fill="both", expand=True, padx=12, pady=(8, 0))
        self.chat = tk.Text(chat_wrap, bg=CARD, fg=TEXT, font=(FONT, 9), wrap="word",
                            height=14, width=1, state="disabled", bd=0, padx=12, pady=10,
                            spacing1=2, spacing3=4, cursor="arrow")
        bar = ttk.Scrollbar(chat_wrap, orient="vertical", command=self.chat.yview)
        self.chat.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.chat.pack(side="left", fill="both", expand=True)
        self.chat.tag_configure("client_head", foreground=ACCENT, font=(FONT, 8, "bold"),
                                spacing1=8)
        self.chat.tag_configure("admin_head", foreground=OK, font=(FONT, 8, "bold"),
                                spacing1=8)
        self.chat.tag_configure("client_body", background=SOFT_BLUE, lmargin1=0, lmargin2=0,
                                rmargin=54, spacing3=8)
        self.chat.tag_configure("admin_body", background=SOFT_GREEN, lmargin1=72,
                                lmargin2=72, spacing3=8)
        self.chat.tag_configure("system", foreground=MUTED, font=(FONT, 8),
                                justify="center", spacing1=8, spacing3=8)

        compose = tk.Frame(self, bg=BG)
        compose.pack(fill="x", padx=12, pady=(8, 0))
        self.txt = tk.Text(compose, height=3, width=1, bg=CARD, fg=TEXT, font=(FONT, 9), wrap="word",
                           bd=1, relief="solid", highlightthickness=0, padx=10, pady=8)
        self.txt.pack(side="left", fill="both", expand=True)
        self.txt.bind("<Control-Return>", lambda _e: (self._send(), "break")[1])
        self.btn_send = tk.Label(compose, text="发送", bg=ACCENT, fg="#FFFFFF", font=(FONT, 9),
                                 padx=18, pady=10, cursor="hand2")
        self.btn_send.pack(side="right", padx=(8, 0), fill="y")
        self.btn_send.bind("<Button-1>", lambda _e: self._send())

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill="x", padx=14, pady=(6, 10))
        self.lbl_status = tk.Label(foot, text="正在连接客服…", bg=BG, fg=MUTED, font=(FONT, 8),
                                   anchor="w")
        self.lbl_status.pack(side="left", fill="x", expand=True)
        tk.Label(foot, text="Ctrl+Enter 发送", bg=BG, fg=MUTED, font=(FONT, 8)).pack(side="right")

    def _set_status(self, text: str, color: str = MUTED) -> None:
        try:
            self.lbl_status.configure(text=text, fg=color)
        except Exception:
            pass

    def _refresh_identity(self) -> None:
        try:
            ev = lic.evaluate()
            code = ev.get("code") or "未生成（发送时自动联网注册）"
            self.lbl_machine.configure(text=f"机器码：{ev.get('machine', '')}")
            self.lbl_code.configure(text=f"注册码：{code}")
        except Exception:
            pass

    def _append(self, message: dict) -> None:
        try:
            mid = int(message.get("id") or 0)
        except Exception:
            mid = 0
        if mid and mid in self._seen:
            return
        if mid:
            self._seen.add(mid)
            self._last_id = max(self._last_id, mid)
        sender = message.get("sender")
        created = str(message.get("created_at") or "")
        clock = created[11:16] if len(created) >= 16 else created
        who = "客服" if sender == "admin" else "我"
        head_tag = "admin_head" if sender == "admin" else "client_head"
        body_tag = "admin_body" if sender == "admin" else "client_body"
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{who} · {clock}\n", head_tag)
        self.chat.insert("end", (message.get("body") or "") + "\n", body_tag)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _append_system(self, text: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", text + "\n", "system")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    # ------------------------------------------------------------ 轮询 / 发送（线程 + 主线程消费）
    def _tick(self) -> None:
        if self._closed:
            return
        if not self._in_flight:
            self._in_flight = True

            def worker() -> None:
                try:
                    data = lic.support_messages(self._last_id, self.version)
                    self._results.put(("poll", data, ""))
                except Exception as exc:  # noqa: BLE001
                    self._results.put(("poll", None, _err_text(exc)))

            threading.Thread(target=worker, daemon=True).start()
        try:
            self._poll_job = self.after(POLL_MS, self._tick)
        except Exception:
            self._poll_job = None

    def _drain(self) -> None:
        if self._closed:
            return
        while True:
            try:
                kind, data, err = self._results.get_nowait()
            except queue.Empty:
                break
            if kind == "poll":
                self._in_flight = False
                self._on_poll(data, err)
            elif kind == "send":
                self._sending = False
                self._on_sent(data, err)
        try:
            self._drain_job = self.after(120, self._drain)
        except Exception:
            self._drain_job = None

    def _on_poll(self, data, err: str) -> None:
        if err:
            self._set_status(f"连接失败：{err}，将自动重试", DANGER)
            return
        if not data or not data.get("ok"):
            self._set_status("客服连接异常，将自动重试", DANGER)
            return
        # 服务端可能刚补发注册码，刷新一次顶部信息不必重建，只更新状态文案。
        self._refresh_identity()
        self._set_status("已连接客服 · 新回复会自动出现", OK)
        for message in data.get("messages") or []:
            self._append(message)
        status = str(data.get("status") or "")
        if status == "closed" and self._last_status != "closed":
            self._append_system("客服会话已标记为结束；继续发送会自动重新打开。")
        self._last_status = status

    def _send(self) -> None:
        if self._sending or self._closed:
            return
        body = self.txt.get("1.0", "end").strip()
        if not body:
            self._set_status("请先输入要咨询的内容", DANGER)
            return
        self._sending = True
        self.btn_send.configure(text="发送中…", bg="#93C5FD")
        self._set_status("正在发送…", MUTED)

        def worker() -> None:
            try:
                data = lic.support_send(body, self.version)
                self._results.put(("send", data, ""))
            except Exception as exc:  # noqa: BLE001
                self._results.put(("send", None, _err_text(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_sent(self, data, err: str) -> None:
        self.btn_send.configure(text="发送", bg=ACCENT)
        if err or not data or not data.get("ok"):
            self._set_status(f"发送失败：{err or '服务端未确认'}", DANGER)
            return
        self.txt.delete("1.0", "end")
        message = data.get("message") or {}
        if message:
            self._append(message)
        self._refresh_identity()
        self._set_status("已发送，客服回复会自动显示在这里", OK)

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for job in (self._poll_job, self._drain_job):
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass
        self.destroy()

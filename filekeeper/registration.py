# -*- coding: utf-8 -*-
"""注册/续费窗口与启动授权闸门。"""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from . import core
from . import license as lic
from . import support as support_ui

FONT = "微软雅黑"
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


def _fmt_remaining(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    if days:
        return f"{days} 天 {hours} 小时"
    if hours:
        return f"{hours} 小时 {mins} 分"
    return f"{mins} 分钟"


class RegistrationDialog(tk.Toplevel):
    def __init__(self, root: tk.Tk, version: str = "", on_close=None):
        super().__init__(root)
        self.version = version
        self.on_close = on_close
        self.result_valid = False
        self._qr_photo = None
        self._order_no = ""
        self._qr_url = ""
        self._creating = False
        self._poll_job = None
        self._support_dlg = None
        self._promo_info: dict = {}
        self.v_promo = tk.StringVar()
        self.title(f"{core.APP_NAME} · 注册 / 续费")
        self.configure(bg=BG)
        self.transient(root)
        self.resizable(False, False)
        self._build()
        self.refresh_display()
        self._center(root)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ------------------------------------------------------------ UI
    def _center(self, root) -> None:
        self.update_idletasks()
        w = 620
        h = min(920, max(640, root.winfo_screenheight() - 80))
        x = root.winfo_rootx() + max(0, (root.winfo_width() - w) // 2)
        y = root.winfo_rooty() + max(0, (root.winfo_height() - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self) -> None:
        head = tk.Frame(self, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        head.pack(fill="x")
        tk.Label(head, text=f"{core.APP_NAME} · 授权", bg=CARD, fg=ACCENT, font=(FONT, 15, "bold")).pack(
            side="left", padx=20, pady=14)
        self.lbl_badge = tk.Label(head, text="", bg=SOFT_BLUE, fg=ACCENT, font=(FONT, 10, "bold"),
                                  padx=10, pady=4)
        self.lbl_badge.pack(side="right", padx=20)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=12)
        self._body_canvas = tk.Canvas(body, bg=BG, highlightthickness=0, bd=0)
        bar = ttk.Scrollbar(body, orient="vertical", command=self._body_canvas.yview)
        self._body_canvas.configure(yscrollcommand=bar.set)
        self._body_canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        inner = tk.Frame(self._body_canvas, bg=BG)
        win = self._body_canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _e: self._body_canvas.configure(
            scrollregion=self._body_canvas.bbox("all")))
        self._body_canvas.bind("<Configure>", lambda e: self._body_canvas.itemconfigure(
            win, width=e.width))
        self.bind("<MouseWheel>", self._wheel)

        box = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="x")
        grid = tk.Frame(box, bg=CARD)
        grid.pack(fill="x", padx=16, pady=12)
        tk.Label(grid, text="机器码", bg=CARD, fg=MUTED, font=(FONT, 9)).grid(row=0, column=0, sticky="w")
        self.v_machine = tk.StringVar()
        e1 = ttk.Entry(grid, textvariable=self.v_machine, state="readonly", width=34)
        e1.grid(row=1, column=0, sticky="w", pady=(2, 8))
        self._btn(grid, "复制", lambda: self._copy(self.v_machine.get())).grid(row=1, column=1, padx=(8, 0), sticky="w")

        tk.Label(grid, text="注册码", bg=CARD, fg=MUTED, font=(FONT, 9)).grid(row=2, column=0, sticky="w")
        self.v_code = tk.StringVar()
        e2 = ttk.Entry(grid, textvariable=self.v_code, state="readonly", width=34)
        e2.grid(row=3, column=0, sticky="w", pady=(2, 8))
        self._btn(grid, "复制", lambda: self._copy(self.v_code.get())).grid(row=3, column=1, padx=(8, 0), sticky="w")

        tk.Label(grid, text="授权状态", bg=CARD, fg=MUTED, font=(FONT, 9)).grid(row=4, column=0, sticky="w")
        self.lbl_state = tk.Label(grid, text="", bg=CARD, fg=TEXT, font=(FONT, 10))
        self.lbl_state.grid(row=5, column=0, sticky="w")
        self.lbl_remain = tk.Label(grid, text="", bg=CARD, fg=MUTED, font=(FONT, 9))
        self.lbl_remain.grid(row=6, column=0, sticky="w", pady=(2, 0))

        # 推广码
        promo = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        promo.pack(fill="x", pady=(10, 0))
        tk.Label(promo, text="推广码（可选）", bg=CARD, fg=MUTED, font=(FONT, 9),
                 anchor="w").pack(fill="x", padx=16, pady=(12, 2))
        prow = tk.Frame(promo, bg=CARD)
        prow.pack(fill="x", padx=16)
        ttk.Entry(prow, textvariable=self.v_promo, width=24).pack(side="left")
        self._btn(prow, "应用", self._apply_promo, primary=True).pack(side="left", padx=(8, 0))
        self._btn(prow, "清除", self._clear_promo).pack(side="left", padx=(6, 0))
        self.lbl_promo = tk.Label(promo, text="有推广码可在此输入，应用后按优惠价付款。",
                                  bg=CARD, fg=MUTED, font=(FONT, 9), anchor="w",
                                  justify="left", wraplength=540)
        self.lbl_promo.pack(fill="x", padx=16, pady=(4, 12))

        # 付款
        pay = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        pay.pack(fill="x", pady=(10, 0))
        self.lbl_price = tk.Label(pay, text="", bg=CARD, fg=TEXT, font=(FONT, 11, "bold"), anchor="w")
        self.lbl_price.pack(fill="x", padx=16, pady=(12, 2))
        self.lbl_notice = tk.Label(pay, text="", bg=CARD, fg=MUTED, font=(FONT, 9), anchor="w",
                                   justify="left", wraplength=540)
        self.lbl_notice.pack(fill="x", padx=16)
        self.lbl_qr = tk.Label(pay, text="收款码未上传，请联系管理员", bg=SOFT_GREY, fg=MUTED,
                               width=25, height=8, font=(FONT, 9), justify="center",
                               wraplength=220)
        self.lbl_qr.pack(pady=8)

        ops = tk.Frame(pay, bg=CARD)
        ops.pack(fill="x", padx=16, pady=(0, 6))
        self.btn_pay = self._btn(ops, "生成专属付款码", self._create_order, primary=True)
        self.btn_pay.pack(side="left")
        self._btn(ops, "我已完成支付", self._paid_clicked).pack(side="left", padx=(8, 0))
        self._btn(ops, "刷新授权状态", self._refresh_clicked).pack(side="left", padx=(8, 0))
        self._btn(ops, "客服", self._open_support).pack(side="left", padx=(8, 0))

        claim = tk.Frame(pay, bg=CARD)
        claim.pack(fill="x", padx=16, pady=(2, 10))
        tk.Label(claim, text="微信交易单号（可选）", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left")
        self.v_txn = tk.StringVar()
        ttk.Entry(claim, textvariable=self.v_txn, width=20).pack(side="left", padx=(6, 6))
        self._btn(claim, "提交凭证", self._claim).pack(side="left")
        self.lbl_order = tk.Label(pay, text="", bg=CARD, fg=ACCENT, font=(FONT, 9), anchor="w",
                                  justify="left", wraplength=520)
        self.lbl_order.pack(fill="x", padx=16, pady=(0, 10))

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill="x", padx=18, pady=(0, 14))
        self.btn_close = self._btn(foot, "关闭", self._close)
        self.btn_close.pack(side="right")
        tk.Label(foot, text=f"服务端：{lic.SERVER}", bg=BG, fg=MUTED, font=(FONT, 8)).pack(side="left")

    def _btn(self, parent, text, cmd, primary: bool = False):
        bg = ACCENT if primary else CARD
        fg = "#FFFFFF" if primary else TEXT
        b = tk.Label(parent, text=text, bg=bg, fg=fg, font=(FONT, 9),
                     padx=12, pady=5, cursor="hand2",
                     highlightthickness=0 if primary else 1,
                     highlightbackground=BORDER)
        b.bind("<Button-1>", lambda _e: cmd())
        return b

    def _wheel(self, event) -> None:
        try:
            self._body_canvas.yview_scroll(int(-event.delta / 120), "units")
        except Exception:
            pass

    # ------------------------------------------------------------ 数据
    def _copy(self, text: str) -> None:
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._flash_order("已复制到剪贴板")

    def refresh_display(self) -> None:
        ev = lic.evaluate()
        self.v_machine.set(ev["machine"])
        self.v_code.set(ev["code"] or "未生成")
        self.lbl_state.configure(text=ev["label"], fg=OK if ev["valid"] else DANGER)
        badge = {"trial": ("试用中", "#FEF3C7", "#B45309"),
                 "active": ("已付费", "#DCFCE7", "#15803D"),
                 "expired": ("已到期", "#FEE2E2", "#B91C1C"),
                 "disabled": ("已停用", "#E5E7EB", "#374151")}.get(ev["state"],
                                                                  ("未激活", "#E5E7EB", "#374151"))
        self.lbl_badge.configure(text=badge[0], bg=badge[1], fg=badge[2])
        self.lbl_remain.configure(
            text=f"到期时间：{ev['end_text']} · 剩余 {_fmt_remaining(ev['remaining'])}" if ev["valid"]
            else "试用 24 小时结束后需订阅；扫码支付后由后台确认开通。")
        price = float(ev.get("price") or 9.9)
        days = int(ev.get("days") or 30)
        promo = self._promo_info or {}
        if promo.get("ok"):
            final = float(promo.get("final_amount") or price)
            self.lbl_price.configure(
                text=f"原价 ¥{price:.2f} / {days} 天 → 推广价 ¥{final:.2f}（{promo.get('benefit_text', '')}）")
            self.lbl_promo.configure(
                text=f"已应用 {promo.get('code', '')}：应付 ¥{final:.2f}，"
                     f"确认收款后额外赠送 {int(promo.get('bonus_days') or 0)} 天。",
                fg=OK)
        else:
            self.lbl_price.configure(text=f"订阅价格：¥{price:.2f} / {days} 天（扫码支付）")
            self.lbl_promo.configure(text="有推广码可在此输入，应用后按优惠价付款。", fg=MUTED)
        self.lbl_notice.configure(text=ev.get("notice") or "扫码支付后点击「我已完成支付」，后台确认到账即自动开通。")
        self.result_valid = bool(ev["valid"])
        self.btn_close.configure(text="继续使用" if ev["valid"] else "退出")

        # 二维码只能由本窗口的下单动作触发；启动时不能显示服务端默认收款码。
        if self._order_no and self._qr_url:
            self._show_qr(self._qr_url, "二维码加载失败\n请点「生成专属付款码」重试")
        else:
            self._qr_url = ""
            self._show_qr("", "点击「生成专属付款码」\n先生成专属付款号，再显示二维码")

    def _show_qr(self, url: str, fallback: str = "二维码加载失败\n请点「生成专属付款码」重试") -> None:
        """按 URL 下载并显示二维码；不同订单使用不同缓存文件，避免显示旧码。"""
        path = lic.qr_image_file(url) if url else ""
        if path and os.path.exists(path):
            try:
                from PIL import Image  # type: ignore
                im = Image.open(path).convert("RGB")
                im.thumbnail((200, 200))
                small = os.path.splitext(path)[0] + "_view.png"
                im.save(small)
                self._qr_photo = tk.PhotoImage(file=small)
                self.lbl_qr.configure(image=self._qr_photo, text="", width=205, height=205, bg=CARD)
                return
            except Exception:
                pass
        self._qr_photo = None
        self.lbl_qr.configure(image="", text=fallback, width=25, height=8, bg=SOFT_GREY)

    def _flash_order(self, text: str) -> None:
        self.lbl_order.configure(text=text)

    def _refresh_clicked(self) -> None:
        ok, msg = lic.sync(self.version)
        self.refresh_display()
        self._flash_order(msg if not ok else "授权状态已更新")
        if self.result_valid and ok:
            pass

    def _open_support(self) -> None:
        dlg = self._support_dlg
        if dlg is not None:
            try:
                if dlg.winfo_exists():
                    dlg.lift()
                    dlg.focus_force()
                    return
            except Exception:
                pass
        self._support_dlg = support_ui.SupportChatDialog(
            self, version=self.version, on_close=self._support_closed)

    def _support_closed(self) -> None:
        self._support_dlg = None
        try:
            self.after(60, self.grab_set)   # 客服窗关闭后恢复注册窗模态
        except Exception:
            pass

    # ------------------------------------------------------------ 订单
    def _apply_promo(self) -> None:
        code = self.v_promo.get().strip().upper()
        if not code:
            self._flash_order("请输入推广码后再应用")
            return
        self.lbl_promo.configure(text="正在校验推广码…", fg=MUTED)
        self.update_idletasks()
        res = lic.promo_validate(code, 1)
        if not res.get("ok"):
            self._promo_info = {}
            self.lbl_promo.configure(text=res.get("error") or "推广码不可用", fg=DANGER)
            self._flash_order(res.get("error") or "推广码不可用")
            return
        self._promo_info = res
        self.v_promo.set(str(res.get("code") or code))
        self.refresh_display()
        self._flash_order(f"推广码已应用：应付 ¥{float(res.get('final_amount') or 0):.2f}")

    def _clear_promo(self) -> None:
        self.v_promo.set("")
        self._promo_info = {}
        self.refresh_display()
        self._flash_order("已清除推广码")

    def _create_order(self) -> None:
        if self._creating:
            return
        self._creating = True
        self.btn_pay.configure(text="正在生成专属付款号…")
        self._flash_order("正在生成专属付款号，请稍候…")
        self.update_idletasks()
        try:
            o = lic.order_create(1, promo_code=self.v_promo.get().strip())
            order_no = str(o.get("order_no") or "").strip()
            if not order_no:
                raise ValueError("服务端未返回订单号")
            self._order_no = order_no
            self._qr_url = o.get("qr_url") or ""
            # 先拿到专属订单号，再显示该订单对应的二维码。
            self._show_qr(self._qr_url, "付款码生成失败\n请点「我已完成支付」或联系管理员")
            self._flash_order(f"订单 {self._order_no} · ¥{o['amount']:.2f}，请用微信扫码；到账后自动开通")
            self._poll_count = 0
            self._poll_paid()
        except Exception as exc:  # noqa: BLE001
            self._order_no = ""
            self._qr_url = ""
            self._show_qr("", "下单失败，请检查网络后重试")
            messagebox.showwarning("下单失败", f"连不上注册服务器：{exc}", parent=self)
        finally:
            self._creating = False
            try:
                self.btn_pay.configure(text="生成专属付款码")
            except Exception:
                pass

    def _paid_clicked(self) -> None:
        """用户表示已支付：立即查单一次，未到账则继续轮询。"""
        if not self._order_no:
            self._flash_order("请先点「生成专属付款码」再扫码支付")
            return
        self._poll_count = 0
        self._poll_paid()

    def _poll_paid(self) -> None:
        if not self._order_no:
            return
        self._poll_count = getattr(self, "_poll_count", 0) + 1
        try:
            st = lic.order_status(self._order_no)
        except Exception:
            st = {}
        if st.get("status") == "paid":
            lic.refresh(self.version)
            self.refresh_display()
            messagebox.showinfo("已开通", "支付已确认，授权已自动续期，感谢支持！", parent=self)
            self._flash_order("支付成功，授权已开通")
            if self.result_valid:
                self.destroy()
                return
        elif st.get("status") == "canceled":
            self._flash_order("订单被标记为未支付/失败，请重新扫码或联系管理员")
            return
        if self._poll_count < 90:
            self._poll_job = self.after(5000, self._poll_paid)

    def _claim(self) -> None:
        if not self._order_no:
            self._flash_order("请先点「生成专属付款码」再提交凭证")
            return
        txn = self.v_txn.get().strip()
        if not txn:
            self._flash_order("请填写微信交易单号后再提交")
            return
        try:
            lic.order_claim(self._order_no, txn)
            self._flash_order("凭证已提交，后台核对后自动开通（可点刷新）")
        except Exception as exc:  # noqa: BLE001
            self._flash_order(f"提交失败：{exc}")

    def _close(self) -> None:
        if self._poll_job:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
        dlg = self._support_dlg
        if dlg is not None:
            try:
                dlg._close()
            except Exception:
                pass
            self._support_dlg = None
        # 关闭窗口不能联网刷新授权；联网最慢 8 秒，会表现为关闭按钮卡住。
        # 这里只读本地缓存，立即关闭；联网校验由 gate 的启动后台线程负责。
        try:
            self.result_valid = bool(lic.evaluate()["valid"])
        except Exception:
            self.result_valid = False
        if self.on_close:
            self.on_close(self.result_valid)
        self.destroy()


def _sync_async(root: tk.Tk, version: str, dlg: RegistrationDialog | None = None) -> None:
    """后台联网校验，避免启动或弹窗被 8 秒网络超时卡住。"""
    done = threading.Event()
    result: dict[str, str] = {}

    def worker() -> None:
        try:
            _ok, msg = lic.sync(version)
        except Exception as exc:  # noqa: BLE001
            msg = f"授权后台校验失败：{exc}"
        result["msg"] = msg
        done.set()

    def apply() -> None:
        if not done.is_set():
            root.after(100, apply)
            return
        if dlg is None:
            return
        try:
            if dlg.winfo_exists():
                dlg.refresh_display()
                dlg._flash_order(result.get("msg", ""))
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()
    root.after(100, apply)


def gate(root: tk.Tk, version: str = "") -> tuple[bool, str]:
    """启动授权闸门：先读本地授权立即放行，联网校验放后台。"""
    ev = lic.evaluate()
    data = lic._load()
    first = not data.get("welcome_shown")

    # 已激活/试用且已展示过欢迎页：不等待网络，后台补同步。
    if ev["valid"] and ev["state"] in ("trial", "active") and not first:
        _sync_async(root, version)
        return True, "本地授权已加载，后台校验中"

    # 首次运行、未激活或已到期：先弹窗，后台同步后自动刷新状态。
    # 主窗默认先隐藏到 UI 构建完成；注册窗 transient 到隐藏主窗会不可见，这里先恢复主窗。
    if not root.winfo_viewable():
        root.deiconify()
        root.update_idletasks()
    dlg = RegistrationDialog(root, version)
    _sync_async(root, version, dlg)
    root.wait_window(dlg)
    if first:
        data["welcome_shown"] = True
        lic._save(data)
    ev2 = lic.evaluate()
    return bool(ev2["valid"]), "本地授权已加载"

# -*- coding: utf-8 -*-
"""注册与授权：机器码、24 小时试用、订阅订单、服务端校验。

服务端地址可用环境变量 FK_SERVER 覆盖（测试用），默认走正式注册后台。
"""
from __future__ import annotations

import base64
import ctypes
import datetime as _dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# 正式构建不允许用环境变量改写服务器或公钥，否则等于留下一条自助绕过授权的后门。
SERVER = "https://sw.olilily.com"
VERSION = "1.5.20.0"
APP_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "FileKeeper")
STATE_PATH = os.path.join(APP_DIR, "license.json")
BRAND_PATH = os.path.join(APP_DIR, "brand_logo.png")
TRIAL_HOURS = 24
GRACE_DAYS = 3          # 已付费用户离线容忍
LEGACY_GRACE_DAYS = 3   # 旧版明文授权缓存的联网升级窗口（越短越安全）
CLOCK_ROLLBACK_DAYS = 2  # 允许的正常时钟误差；再往回拨视为异常
TIMEOUT = 8

# Ed25519 公钥（私钥只保存在注册服务器）。公钥指纹在导入时自检，防止误配。
LICENSE_PUBKEY_B64 = "bUDNIX11zxTTd2g4efiFDGQjDDf2P513mY5YON/TVbE="
LICENSE_PUBKEY_SHA256 = "bf7049fadfd273e41cc8ad90c8c5aef3a161363deeec26d238c25a43bbc21d6c"
LICENSE_SIG_VER = "ed25519-1"
LICENSE_PUBKEY = Ed25519PublicKey.from_public_bytes(
    base64.b64decode(LICENSE_PUBKEY_B64))
_pubkey_fp = hashlib.sha256(base64.b64decode(LICENSE_PUBKEY_B64)).hexdigest()
if _pubkey_fp != LICENSE_PUBKEY_SHA256:
    raise RuntimeError("授权公钥指纹不匹配，拒绝启动")

_cache: dict | None = None
_machine_cache: str | None = None


# ---------------------------------------------------------------- 机器码
def _volume_serial() -> str:
    try:
        serial = ctypes.c_ulong()
        fs = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p("C:\\"), None, 0,
            ctypes.byref(serial), ctypes.byref(fs), None, None, 0)
        return f"{serial.value:08X}" if ok else ""
    except Exception:
        return ""


def _machine_guid() -> str:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Cryptography", 0,
                            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)) as k:
            return str(winreg.QueryValueEx(k, "MachineGuid")[0])
    except Exception:
        return ""


def _cpu_name() -> str:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            return str(winreg.QueryValueEx(k, "ProcessorNameString")[0])
    except Exception:
        return platform.processor() or ""


def machine_id() -> str:
    """机器码：Windows 安装号 + CPU + 主板/网卡信息做摘要，重装软件不变。"""
    global _machine_cache
    if _machine_cache:
        return _machine_cache
    raw = "|".join([_machine_guid(), _cpu_name(), _volume_serial(), f"{uuid.getnode():012X}"])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()[:16]
    _machine_cache = "-".join(digest[i:i + 4] for i in range(0, 16, 4))
    return _machine_cache


# ---------------------------------------------------------------- 本地缓存
def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    except Exception:
        _cache = {}
    return _cache


def _restrict_permissions(path: str) -> None:
    """把授权缓存限制为当前 Windows 用户可读写，降低同机其他账户篡改机会。"""
    if os.name != "nt":
        return
    user = (os.environ.get("USERNAME") or "").strip()
    if not user:
        return
    try:
        subprocess.run(
            ["icacls", path, "/inheritance:r", "/grant:r", f"{user}:F"],
            check=False, timeout=5,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass


def _save(data: dict) -> None:
    global _cache
    _cache = dict(data)
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=2)
        os.replace(tmp, STATE_PATH)
        _restrict_permissions(STATE_PATH)
    except Exception:
        pass


def _post(path: str, payload: dict) -> dict:
    url = SERVER.rstrip("/") + path
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str) -> dict:
    url = SERVER.rstrip("/") + path
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_brand_logo() -> bool:
    """从后台拉取品牌横版图到本地缓存。

    返回 True 表示缓存发生变化；404 表示后台恢复默认，会删除本地远端缓存。
    网络失败不影响启动，继续使用已有缓存或内置默认图。
    """
    url = SERVER.rstrip("/") + "/api/brand/logo?ts=" + str(int(time.time()))
    req = urllib.request.Request(url, headers={"User-Agent": f"WenWen/{VERSION}"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            if os.path.exists(BRAND_PATH):
                try:
                    os.remove(BRAND_PATH)
                except OSError:
                    pass
                return True
        return False
    except Exception:
        return False
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 8 * 1024 * 1024:
        return False
    try:
        if os.path.exists(BRAND_PATH):
            with open(BRAND_PATH, "rb") as f:
                if f.read() == data:
                    return False
        os.makedirs(APP_DIR, exist_ok=True)
        tmp = BRAND_PATH + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, BRAND_PATH)
        return True
    except Exception:
        return False


def _canonical_payload(data: dict) -> bytes:
    fields = ("machine", "code", "state", "trial_end", "license_end",
              "server_time", "price", "days", "payee", "notice",
              "qr_url", "remaining_seconds")
    body = {k: data.get(k) for k in fields}
    return json.dumps(body, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _verify_signature(data: dict) -> bool:
    sig = data.get("sig")
    if not sig or data.get("sig_ver") != LICENSE_SIG_VER:
        return False
    try:
        LICENSE_PUBKEY.verify(base64.b64decode(sig, validate=True),
                              _canonical_payload(data))
    except (InvalidSignature, ValueError, TypeError):
        return False
    return str(data.get("machine") or "") == machine_id()


def _legacy_grace_ok(data: dict) -> bool:
    """兼容 v1.5.7 及更早的明文缓存：最近 7 天内同步过的老用户先放行一次。"""
    if data.get("sig"):
        return False
    if not data.get("code") or str(data.get("machine") or "") != machine_id():
        return False
    last_sync = _parse(data.get("last_sync"))
    return bool(last_sync and _dt.datetime.now() <= last_sync + _dt.timedelta(days=LEGACY_GRACE_DAYS))


def _merge(payload: dict) -> dict:
    payload = dict(payload)
    if not _verify_signature(payload):
        raise ValueError("授权服务器签名校验失败")
    data = _load()
    data.update({k: v for k, v in payload.items() if k not in ("ok",)})
    data["machine"] = payload.get("machine") or data.get("machine") or machine_id()
    data["last_sync"] = time.strftime("%Y-%m-%d %H:%M:%S")
    data["local_machine"] = machine_id()
    data.pop("sig_grace_until", None)
    _save(data)
    return data


def register(version: str = "") -> dict:
    """首次运行或本地无记录时调用：服务端生成注册码并开 24 小时试用。"""
    return _merge(_post("/api/register", {"machine": machine_id(), "version": version}))


def refresh(version: str = "") -> dict:
    data = _load()
    if not data.get("code"):
        return register(version)
    try:
        return _merge(_post("/api/status", {"machine": machine_id(), "version": version}))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:          # 服务端记录丢失（换机/清库）时自动重新注册
            return register(version)
        raise


# ---------------------------------------------------------------- 在线客服
def _support_identity(version: str = "") -> tuple[str, str]:
    """返回 (机器码, 注册码)。无注册码时先联网注册，仍失败则抛错。"""
    data = _load()
    if not data.get("code"):
        data = refresh(version or VERSION)
    code = str(data.get("code") or "").strip()
    if not code:
        raise RuntimeError("尚未取得注册码，请先联网注册")
    return machine_id(), code


def support_send(body: str, version: str = "") -> dict:
    machine, code = _support_identity(version)
    return _post("/api/support/send", {
        "machine": machine, "code": code, "version": version or VERSION,
        "body": body,
    })


def support_messages(after: int = 0, version: str = "") -> dict:
    machine, code = _support_identity(version)
    query = urllib.parse.urlencode({
        "machine": machine, "code": code, "version": version or VERSION,
        "after": max(0, int(after or 0)),
    })
    return _get("/api/support/messages?" + query)


def order_create(months: int = 1, promo_code: str = "") -> dict:
    data = _load()
    payload = {"machine": machine_id(), "months": months,
               "code": data.get("code", "")}
    promo = (promo_code or "").strip()
    if promo:
        payload["promo_code"] = promo
    return _post("/api/order", payload)


def promo_validate(code: str, months: int = 1) -> dict:
    code = (code or "").strip()
    if not code:
        return {"ok": False, "error": "请输入推广码"}
    try:
        return _post("/api/promo/validate", {
            "machine": machine_id(), "months": months, "code": code,
        })
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:
            body = {}
        return {"ok": False, "error": body.get("error") or f"校验失败（HTTP {exc.code}）"}
    except Exception as exc:
        return {"ok": False, "error": f"无法连接授权服务：{exc}"}


def order_status(order_no: str) -> dict:
    return _get(f"/api/order/{order_no}")


def order_claim(order_no: str, txn: str) -> dict:
    return _post(f"/api/order/{order_no}/claim", {"txn": txn})


# ---------------------------------------------------------------- 状态判定
def _parse(s: str | None) -> _dt.datetime | None:
    try:
        return _dt.datetime.strptime((s or "")[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _clock_rollback(data: dict) -> bool:
    """已签名授权带服务端时间；本机时间明显早于它时判定为时钟回拨。"""
    server_time = _parse(data.get("server_time"))
    if not server_time:
        return False
    return _dt.datetime.now() < server_time - _dt.timedelta(days=CLOCK_ROLLBACK_DAYS)


def evaluate(data: dict | None = None) -> dict:
    """返回 {state, expires, remaining_seconds, valid, label, code, machine, price, days}"""
    data = data or _load()
    signed_ok = _verify_signature(data)
    if signed_ok and _clock_rollback(data):
        return {"state": "invalid", "valid": False, "expires": None, "remaining": 0,
                "end_text": "—", "label": "系统时间异常，请校准时间后联网重新激活",
                "code": data.get("code", ""), "machine": data.get("machine", "") or machine_id(),
                "price": data.get("price", 9.9), "days": data.get("days", 30),
                "notice": data.get("notice", ""), "payee": data.get("payee", ""),
                "qr_url": data.get("qr_url", SERVER.rstrip("/") + "/qr.png"),
                "offline": bool(data.get("offline"))}
    if not signed_ok and not _legacy_grace_ok(data):
        return {"state": "invalid", "valid": False, "expires": None, "remaining": 0,
                "end_text": "—", "label": "授权校验失败，请联网重新激活",
                "code": data.get("code", ""), "machine": data.get("machine", "") or machine_id(),
                "price": data.get("price", 9.9), "days": data.get("days", 30),
                "notice": data.get("notice", ""), "payee": data.get("payee", ""),
                "qr_url": data.get("qr_url", SERVER.rstrip("/") + "/qr.png"),
                "offline": bool(data.get("offline"))}
    st = data.get("state") or "unknown"
    lic_end = _parse(data.get("license_end"))
    trial_end = _parse(data.get("trial_end"))
    now = _dt.datetime.now()
    if st == "disabled":
        valid = False
        expires = lic_end
    elif lic_end and lic_end > now:
        valid, expires = True, lic_end
    elif st == "active" and lic_end and (now - lic_end).days <= GRACE_DAYS:
        valid, expires = True, lic_end       # 离线宽限
    elif trial_end and trial_end > now:
        valid, expires, st = True, trial_end, "trial"
    else:
        valid, expires = False, lic_end or trial_end
        if st in ("active", "trial"):
            st = "expired"
    remaining = int((expires - now).total_seconds()) if expires else 0
    end_txt = expires.strftime("%Y-%m-%d %H:%M") if expires else "—"
    if st == "trial" and valid:
        left = max(0, remaining)
        if left < 3600:
            label = f"试用中 · 剩 {left // 60} 分钟"
        else:
            label = f"试用中 · 剩 {left // 3600} 小时 {left % 3600 // 60} 分"
    elif st == "active" and valid:
        if lic_end and lic_end < now:
            label = f"已付费 · 到期后离线宽限中（{end_txt} 到期）"
        else:
            label = f"已付费 · 有效期至 {end_txt}"
    elif st == "disabled":
        label = "授权已停用"
    else:
        label = f"授权已到期（{end_txt if expires else '未激活'}）"
    return {"state": st, "valid": valid, "expires": expires, "remaining": remaining,
            "end_text": end_txt, "label": label,
            "code": data.get("code", ""), "machine": data.get("machine", "") or machine_id(),
            "price": data.get("price", 9.9), "days": data.get("days", 30),
            "notice": data.get("notice", ""), "payee": data.get("payee", ""),
            "qr_url": data.get("qr_url", SERVER.rstrip("/") + "/qr.png"),
            "offline": bool(data.get("offline"))}


def sync(version: str = "") -> tuple[bool, str]:
    """联网同步；失败则退回本地缓存。返回 (是否成功联网, 说明)。"""
    try:
        refresh(version)
        data = _load()
        data["offline"] = False
        _save(data)
        return True, "已连接注册服务器"
    except Exception as exc:  # noqa: BLE001
        data = _load()
        data["offline"] = True
        _save(data)
        return False, f"连不上注册服务器（{type(exc).__name__}），按本地授权继续"


def qr_image_file(url: str) -> str:
    """下载收款码到临时文件供 Tk 显示；按 URL 区分，换订单立即刷新。"""
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        key = hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:12]
        path = os.path.join(APP_DIR, f"pay_qr_{key}.png")
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < 3600:
            return path
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            raw = resp.read()
        if not raw:
            return ""
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(raw)
        os.replace(tmp, path)
        return path
    except Exception:
        return ""


def summary_line() -> str:
    ev = evaluate()
    if ev["offline"]:
        return ev["label"] + "（离线校验）"
    return ev["label"]










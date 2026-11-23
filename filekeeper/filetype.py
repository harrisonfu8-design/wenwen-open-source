# -*- coding: utf-8 -*-
"""文件类型两层识别。

第一层：按扩展名快速判断，保证常见文件零开销。
第二层：读取文件头 / 压缩容器结构，校验真实格式；扩展名伪装、缺失或
损坏时，以内容证据纠正类型。识别结果只用于选择解析器和给出提示，不改动
原文件内容。
"""
from __future__ import annotations

import os
import zipfile
from typing import Any, Dict, Optional

# 扩展名 -> 格式族。族比扩展名粗，便于同一类格式互相校验。
EXT_FAMILY: Dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx", ".doc": "doc", ".rtf": "rtf", ".odt": "odt",
    ".xlsx": "xlsx", ".xlsm": "xlsx", ".xls": "xls",
    ".pptx": "pptx", ".ppt": "ppt",
    ".ofd": "ofd",
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".bmp": "image",
    ".gif": "image", ".webp": "image", ".tif": "image", ".tiff": "image",
    ".heic": "image", ".heif": "image", ".avif": "image",
    ".mp4": "video", ".mov": "video", ".m4v": "video", ".avi": "video",
    ".mkv": "video", ".webm": "video", ".wmv": "video", ".flv": "video",
    ".mp3": "audio", ".wav": "audio", ".flac": "audio", ".aac": "audio",
    ".m4a": "audio", ".ogg": "audio",
    ".zip": "archive", ".rar": "archive", ".7z": "archive",
    ".tar": "archive", ".gz": "archive", ".bz2": "archive",
    ".txt": "text", ".md": "text", ".markdown": "text", ".csv": "text",
    ".log": "text", ".json": "text", ".xml": "text", ".html": "text",
    ".htm": "text", ".ini": "text", ".yaml": "text", ".yml": "text",
    ".sql": "text", ".py": "text", ".js": "text", ".ts": "text",
    ".css": "text", ".bat": "text", ".ps1": "text", ".sh": "text",
    ".java": "text", ".c": "text", ".cpp": "text", ".h": "text",
    ".cs": "text", ".php": "text", ".go": "text",
    ".db": "database", ".sqlite": "database", ".sqlite3": "database",
    ".exe": "executable", ".dll": "executable",
}

FAMILY_KIND: Dict[str, str] = {
    "pdf": "PDF 文档",
    "docx": "Word 文档", "doc": "Word 文档（旧版）", "rtf": "RTF 文档", "odt": "ODT 文档",
    "xlsx": "表格", "xls": "表格（旧版）",
    "pptx": "演示文稿", "ppt": "演示文稿（旧版）",
    "ofd": "OFD 电子发票",
    "image": "图片", "video": "视频", "audio": "音频", "archive": "压缩包",
    "text": "文本", "database": "数据库", "executable": "可执行文件",
    "ole": "OLE 复合文档", "empty": "空文件", "unknown": "未知类型",
}

# 同义扩展名：签名相同但后缀写法不同，不视为伪装。
EQUIVALENT_EXT: Dict[str, set] = {
    ".jpg": {".jpg", ".jpeg"},
    ".jpeg": {".jpg", ".jpeg"},
    ".tif": {".tif", ".tiff"},
    ".tiff": {".tif", ".tiff"},
    ".md": {".md", ".markdown"},
    ".markdown": {".md", ".markdown"},
    ".html": {".html", ".htm"},
    ".htm": {".html", ".htm"},
    ".heic": {".heic", ".heif"},
    ".heif": {".heic", ".heif"},
    ".xlsx": {".xlsx", ".xlsm"},
    ".xlsm": {".xlsx", ".xlsm"},
    ".sqlite": {".sqlite", ".sqlite3", ".db"},
    ".sqlite3": {".sqlite", ".sqlite3", ".db"},
    ".db": {".sqlite", ".sqlite3", ".db"},
    ".exe": {".exe", ".dll"},
    ".dll": {".exe", ".dll"},
}

# 这些格式有明确的结构头；有扩展名但签名缺失时提示可能损坏。
STRUCTURED_EXT = {".pdf", ".docx", ".xlsx", ".xlsm", ".pptx", ".ofd",
                  ".zip", ".rar", ".7z"}

MAX_HEAD = 256 * 1024
MAX_ZIP_INSPECT = 200 * 1024 * 1024


def _u16(s: str) -> bytes:
    return s.encode("utf-16le")


def _read_head(path: str, limit: int = MAX_HEAD) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read(limit)
    except OSError:
        return b""


def _text_like(data: bytes) -> bool:
    """是否是大概率可读的纯文本；二进制控制字符过多则否定。"""
    if not data:
        return False
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return True
    sample = data[:8192]
    if b"\x00" in sample:
        return False
    for enc in ("utf-8", "gb18030", "big5"):
        try:
            s = sample.decode(enc, errors="strict")
        except (UnicodeDecodeError, LookupError):
            continue
        if not s:
            return False
        good = sum(1 for ch in s if ch.isprintable() or ch in "\r\n\t")
        return good / len(s) >= 0.85
    return False


def _zip_signature(path: str, size: int) -> Optional[Dict[str, str]]:
    if size > MAX_ZIP_INSPECT:
        return {"family": "archive", "ext": ".zip", "kind": "压缩包"}
    try:
        if not zipfile.is_zipfile(path):
            return None
    except Exception:
        return None
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
    except Exception:
        # 加密 ZIP / 特殊压缩包：容器头成立，内容清单读不到也仍按 ZIP
        return {"family": "archive", "ext": ".zip", "kind": "压缩包"}
    if "OFD.xml" in names:
        return {"family": "ofd", "ext": ".ofd", "kind": "OFD 电子发票"}
    if "word/document.xml" in names:
        return {"family": "docx", "ext": ".docx", "kind": "Word 文档"}
    if "xl/workbook.xml" in names:
        return {"family": "xlsx", "ext": ".xlsx", "kind": "表格"}
    if "ppt/presentation.xml" in names:
        return {"family": "pptx", "ext": ".pptx", "kind": "演示文稿"}
    if "content.xml" in names and "META-INF/manifest.xml" in names:
        return {"family": "odt", "ext": ".odt", "kind": "ODT 文档"}
    return {"family": "archive", "ext": ".zip", "kind": "压缩包"}


def _sniff(path: str, head: bytes, size: int) -> Optional[Dict[str, str]]:
    """第二层：按文件头与容器结构识别真实格式。"""
    if not head:
        return None

    # PDF 允许头部前有少量空白/注释，规范要求前 1024 字节内出现 %PDF-
    pos = head.find(b"%PDF-", 0, 1024)
    if pos >= 0:
        return {"family": "pdf", "ext": ".pdf", "kind": "PDF 文档"}

    # ZIP / OOXML / OFD：不能只看 PK，必须看容器里的标志文件
    if head[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
        z = _zip_signature(path, size)
        if z:
            return z

    # OLE 复合文档：旧版 Word / Excel / PPT
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        if b"WordDocument" in head or _u16("WordDocument") in head:
            return {"family": "doc", "ext": ".doc", "kind": "Word 文档（旧版）"}
        if b"Workbook" in head or _u16("Workbook") in head:
            return {"family": "xls", "ext": ".xls", "kind": "表格（旧版）"}
        if b"PowerPoint Document" in head or _u16("PowerPoint Document") in head:
            return {"family": "ppt", "ext": ".ppt", "kind": "演示文稿（旧版）"}

    # 图片
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return {"family": "image", "ext": ".png", "kind": "图片"}
    if head.startswith(b"\xff\xd8\xff"):
        return {"family": "image", "ext": ".jpg", "kind": "图片"}
    if head.startswith((b"GIF87a", b"GIF89a")):
        return {"family": "image", "ext": ".gif", "kind": "图片"}
    if head.startswith(b"BM"):
        return {"family": "image", "ext": ".bmp", "kind": "图片"}
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return {"family": "image", "ext": ".tiff", "kind": "图片"}
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return {"family": "image", "ext": ".webp", "kind": "图片"}

    # ISO Base Media（mp4/mov/m4a/heic/avif）：看 ftyp 主品牌
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"):
            return {"family": "image", "ext": ".heic", "kind": "图片"}
        if brand == b"avif":
            return {"family": "image", "ext": ".avif", "kind": "图片"}
        if brand in (b"M4A ", b"M4B ", b"M4P "):
            return {"family": "audio", "ext": ".m4a", "kind": "音频"}
        if brand in (b"qt  ", b"M4V ", b"M4VP"):
            return {"family": "video", "ext": ".mov", "kind": "视频"}
        if brand in (b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"3gp4", b"dash"):
            return {"family": "video", "ext": ".mp4", "kind": "视频"}

    # 视频 / 音频容器
    if head.startswith(b"\x1aE\xdf\xa3"):
        return {"family": "video", "ext": ".mkv", "kind": "视频"}
    if head.startswith(b"RIFF") and head[8:12] == b"AVI ":
        return {"family": "video", "ext": ".avi", "kind": "视频"}
    if head.startswith(b"FLV"):
        return {"family": "video", "ext": ".flv", "kind": "视频"}
    if head.startswith(b"0&\xb2u\x8ef\xcf\x11\xa6\xd9\x00\xaa\x00b\xcel"):
        return {"family": "video", "ext": ".wmv", "kind": "视频"}
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return {"family": "audio", "ext": ".wav", "kind": "音频"}
    if head.startswith(b"ID3"):
        return {"family": "audio", "ext": ".mp3", "kind": "音频"}
    if head.startswith(b"fLaC"):
        return {"family": "audio", "ext": ".flac", "kind": "音频"}
    if head.startswith(b"OggS"):
        return {"family": "audio", "ext": ".ogg", "kind": "音频"}

    # 压缩包
    if head.startswith(b"Rar!\x1a\x07"):
        return {"family": "archive", "ext": ".rar", "kind": "压缩包"}
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return {"family": "archive", "ext": ".7z", "kind": "压缩包"}
    if head.startswith(b"\x1f\x8b"):
        return {"family": "archive", "ext": ".gz", "kind": "压缩包"}
    if head.startswith(b"BZh"):
        return {"family": "archive", "ext": ".bz2", "kind": "压缩包"}
    if len(head) >= 265 and head[257:262] == b"ustar":
        return {"family": "archive", "ext": ".tar", "kind": "压缩包"}

    # 数据库
    if head.startswith(b"SQLite format 3\x00"):
        return {"family": "database", "ext": ".sqlite", "kind": "数据库"}

    # 可执行文件
    if head.startswith(b"MZ"):
        return {"family": "executable", "ext": ".exe", "kind": "可执行文件"}

    # RTF / HTML：属于文本类，但给更准确的提示
    if head.lstrip().startswith(b"{\\rtf"):
        return {"family": "rtf", "ext": ".rtf", "kind": "RTF 文档"}
    low = head[:512].lstrip().lower()
    if low.startswith(b"<!doctype html") or low.startswith(b"<html"):
        return {"family": "text", "ext": ".html", "kind": "文本"}

    return None


def detect(path: str, name: Optional[str] = None) -> Dict[str, Any]:
    """返回类型识别结果。

    关键字段：ext 真实扩展名、family 格式族、kind 展示名称、
    source 判定依据、mismatch 扩展名是否与内容不符、note 提示。
    """
    name = name or os.path.basename(path)
    ext1 = os.path.splitext(name)[1].lower()
    family1 = EXT_FAMILY.get(ext1, "unknown")
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0

    result: Dict[str, Any] = {
        "ext": ext1,
        "original_ext": ext1,
        "family": family1,
        "kind": FAMILY_KIND.get(family1, "未知类型"),
        "source": "扩展名" if ext1 else "无扩展名",
        "mismatch": False,
        "note": "",
        "damaged": False,
        "size": size,
    }
    if size == 0:
        result.update(family="empty", kind="空文件", source="文件大小")
        return result

    head = _read_head(path)
    sig = _sniff(path, head, size)

    if sig:
        f2, e2 = sig["family"], sig["ext"]
        same_family = family1 == f2
        # 文本类后缀差异不纠正（.txt/.md/.json 都按文本处理）
        text_family = family1 == "text" and f2 == "text"
        equivalent = ext1 in EQUIVALENT_EXT.get(e2, {e2})
        if family1 == "unknown" or family1 == "":
            result.update(ext=e2, family=f2, kind=sig["kind"], source="内容签名")
        elif same_family and (equivalent or text_family):
            result.update(source="签名校验", kind=sig["kind"])
        elif same_family:
            result.update(ext=e2, family=f2, kind=sig["kind"], source="内容签名",
                          mismatch=True,
                          note=f"扩展名 {ext1 or '（无）'} 与实际内容 {e2} 不符，已按实际格式处理")
        else:
            result.update(ext=e2, family=f2, kind=sig["kind"], source="内容签名",
                          mismatch=True,
                          note=f"扩展名 {ext1 or '（无）'} 与实际内容 {e2} 不符，已按实际格式处理")
        return result

    # 没有可识别签名：已知扩展名优先保留；未知扩展名再看是否纯文本
    if family1 != "unknown":
        result["source"] = "扩展名"
        if ext1 in STRUCTURED_EXT:
            result["damaged"] = True
            result["note"] = f"文件头不符合 {ext1} 格式，可能已损坏"
        return result

    if _text_like(head):
        result.update(ext=ext1 or ".txt", family="text", kind="文本",
                      source="内容文本")
        return result

    result.update(family="unknown", kind="未知类型", source="无法识别")
    return result

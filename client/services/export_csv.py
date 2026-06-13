"""轻量 CSV 导出辅助。

不依赖 pandas，直接用 stdlib csv 写到 StringIO，再返回 StreamingResponse。
"""

import csv
import io
from datetime import datetime
from typing import Iterable, Sequence


def to_csv_bytes(headers: Sequence[str], rows: Iterable[Sequence]) -> bytes:
    """把 [header, header...] + 多行 [val, val...] 转成 CSV bytes（带 UTF-8 BOM，方便 Excel 打开）。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([
            "" if v is None else (
                v.isoformat() if isinstance(v, datetime) else str(v)
            )
            for v in row
        ])
    # 加 UTF-8 BOM，让 Excel 能正确识别中文
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def filename_with_ts(prefix: str, ext: str = "csv") -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

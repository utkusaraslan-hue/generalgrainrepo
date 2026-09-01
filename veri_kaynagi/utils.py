"""Ortak yardimci fonksiyonlar: TR sayi formati parse etme, zaman damgasi."""
from datetime import datetime, timezone

# Bazi borsa siteleri User-Agent gondermeyen istekleri reddediyor (connection reset).
TARAYICI_BASLIKLARI = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def tr_sayi(deger) -> float | None:
    """'17.172,50' -> 17172.50 ; '-' veya bos -> None"""
    if deger is None:
        return None
    if isinstance(deger, (int, float)):
        return float(deger)
    s = str(deger).strip()
    if s in ("", "-", "0", None):
        return None if s in ("", "-") else 0.0
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def simdi_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

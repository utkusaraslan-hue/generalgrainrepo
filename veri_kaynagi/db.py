"""SQLite depolama katmani. Tum kaynaklardan gelen fiyat verilerini tek, normallestirilmis tabloda tutar."""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "borsa_verileri.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS fiyatlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kaynak TEXT NOT NULL,
    tarih TEXT NOT NULL,
    il TEXT,
    ilce TEXT,
    urun TEXT,
    detay TEXT,
    min_fiyat REAL,
    ort_fiyat REAL,
    max_fiyat REAL,
    kapanis_fiyat REAL,
    miktar REAL,
    birim TEXT,
    ham_veri TEXT,
    cekilme_zamani TEXT NOT NULL,
    UNIQUE(kaynak, tarih, urun, detay, il, ilce)
);
CREATE INDEX IF NOT EXISTS idx_fiyatlar_tarih ON fiyatlar(tarih);
CREATE INDEX IF NOT EXISTS idx_fiyatlar_kaynak ON fiyatlar(kaynak);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def upsert_kayitlar(conn: sqlite3.Connection, kayitlar: list[dict]) -> int:
    """kayitlar: fiyatlar tablosunun kolonlariyla eslesen dict listesi. Ayni gun tekrar
    calistirilirsa UNIQUE kisit sayesinde eski kayit guncellenir (idempotent)."""
    cols = ["kaynak", "tarih", "il", "ilce", "urun", "detay", "min_fiyat", "ort_fiyat",
            "max_fiyat", "kapanis_fiyat", "miktar", "birim", "ham_veri", "cekilme_zamani"]
    sql = f"""INSERT INTO fiyatlar ({",".join(cols)}) VALUES ({",".join("?" * len(cols))})
              ON CONFLICT(kaynak, tarih, urun, detay, il, ilce) DO UPDATE SET
              min_fiyat=excluded.min_fiyat, ort_fiyat=excluded.ort_fiyat, max_fiyat=excluded.max_fiyat,
              kapanis_fiyat=excluded.kapanis_fiyat, miktar=excluded.miktar, birim=excluded.birim,
              ham_veri=excluded.ham_veri, cekilme_zamani=excluded.cekilme_zamani"""
    # SQLite'ta UNIQUE kisiti NULL degerleri "hep farkli" sayar, yani
    # kisitin bir parcasi olan urun/detay/il/ilce alanlari NULL kalirsa
    # ayni gun tekrar calistirmak upsert yerine hep yeni satir ekler.
    # Bu yuzden kisit alanlarindaki None'lari bos string'e ceviriyoruz.
    kisit_alanlari = {"urun", "detay", "il", "ilce"}
    rows = []
    for k in kayitlar:
        ham = k.get("ham_veri")
        if ham is not None and not isinstance(ham, str):
            ham = json.dumps(ham, ensure_ascii=False)
        deger = lambda c: ham if c == "ham_veri" else (
            k.get(c) if k.get(c) is not None or c not in kisit_alanlari else ""
        )
        rows.append(tuple(deger(c) for c in cols))
    with conn:
        conn.executemany(sql, rows)
    return len(rows)

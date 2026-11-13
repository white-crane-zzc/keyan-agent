"""SQLite 存储层：论文元信息、段落、参考文献、翻译缓存、推荐与反馈。"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL,
    path        TEXT NOT NULL,
    sha256      TEXT,
    minhash     TEXT,
    title       TEXT,
    authors     TEXT,
    year        TEXT,
    n_pages     INTEGER DEFAULT 0,
    n_chars     INTEGER DEFAULT 0,
    size        INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'ready',
    meta_json   TEXT,
    added_at    TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS chunks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id  INTEGER NOT NULL,
    page      INTEGER,
    section   TEXT,
    ordinal   INTEGER,
    text      TEXT,
    FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS refs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id    INTEGER NOT NULL,
    raw         TEXT,
    title       TEXT,
    authors     TEXT,
    year        TEXT,
    arxiv_id    TEXT,
    linked_id   INTEGER,
    FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS translations (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id  INTEGER NOT NULL,
    chunk_id  INTEGER,
    lang      TEXT DEFAULT 'zh',
    source    TEXT,
    text      TEXT,
    at        TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(paper_id, chunk_id, lang)
);
CREATE TABLE IF NOT EXISTS recs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    arxiv_id  TEXT UNIQUE,
    title     TEXT,
    summary   TEXT,
    pdf_url   TEXT,
    score     REAL,
    reason    TEXT,
    has_code  INTEGER DEFAULT 0,
    feedback  TEXT,
    at        TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_chunks_paper ON chunks(paper_id);
CREATE INDEX IF NOT EXISTS idx_refs_paper ON refs(paper_id);
"""


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def q(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with conn() as c:
        return c.execute(sql, tuple(params)).fetchall()


def one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    with conn() as c:
        return c.execute(sql, tuple(params)).fetchone()


def exec_(sql: str, params: Iterable[Any] = ()) -> int:
    with conn() as c:
        cur = c.execute(sql, tuple(params))
        return cur.lastrowid or cur.rowcount


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)

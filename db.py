"""Banco de dados SQLite assíncrono unificado para o Bot Colizeu."""
import aiosqlite
import logging
from pathlib import Path
from config import DATABASE_PATH

log = logging.getLogger("colizeu.db")

SCHEMA = """
-- Domínio: Usuários & Progressão
CREATE TABLE IF NOT EXISTS usr_users (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER NOT NULL DEFAULT 0,
    nivel INTEGER NOT NULL DEFAULT 1,
    denarios INTEGER NOT NULL DEFAULT 0,
    patente TEXT,
    last_xp_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usr_perfis (
    user_id INTEGER PRIMARY KEY,
    thread_id INTEGER,
    card_msg_id INTEGER,
    tagline TEXT,
    bio TEXT,
    fav_game TEXT,
    theme TEXT DEFAULT 'Ouro',
    links JSON,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Domínio: Conquistas (Platinas + Zerados)
CREATE TABLE IF NOT EXISTS plat_conquistas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    tipo TEXT NOT NULL CHECK(tipo IN ('platina', 'zerado')),
    game TEXT NOT NULL,
    platform TEXT,
    earned_at DATE,
    comentario TEXT,
    proof_msg_id INTEGER,
    proof_url TEXT,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
    xp_awarded INTEGER DEFAULT 0,
    denarios_awarded INTEGER DEFAULT 0,
    reviewer_id INTEGER,
    reject_reason TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Domínio: Soulslike Runs
CREATE TABLE IF NOT EXISTS sl_games (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS sl_challenges (id INTEGER PRIMARY KEY, name TEXT UNIQUE, rules TEXT);
CREATE TABLE IF NOT EXISTS sl_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    game_id INTEGER NOT NULL,
    challenge_id INTEGER NOT NULL,
    seconds INTEGER NOT NULL,
    build TEXT,
    status TEXT DEFAULT 'pending',
    proof_msg_id INTEGER,
    proof_url TEXT,
    reviewer_id INTEGER,
    reject_reason TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Domínio: Catálogo
CREATE TABLE IF NOT EXISTS cat_jogos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    descricao TEXT,
    plataformas TEXT,
    tags TEXT,
    status TEXT DEFAULT 'ativo',
    adicionado_por INTEGER,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Domínio: Configuração & Estado
CREATE TABLE IF NOT EXISTS cfg_painels (
    key TEXT PRIMARY KEY,
    channel_id INTEGER,
    message_id INTEGER,
    marker TEXT,
    config JSON,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cfg_sent_offers (
    item_key TEXT PRIMARY KEY,
    sent_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cfg_youtube_state (
    channel_id TEXT PRIMARY KEY,
    last_video_id TEXT,
    last_live_id TEXT,
    checked_at TIMESTAMP
);

-- Logs de Auditoria
CREATE TABLE IF NOT EXISTS sys_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self):
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(DATABASE_PATH)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()
        log.info("Banco de dados conectado e schema aplicado em %s", DATABASE_PATH)

    async def close(self):
        if self.conn:
            await self.conn.close()
            log.info("Conexão com banco de dados encerrada.")

    async def _one(self, sql: str, params: tuple = ()):
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchone()

    async def _all(self, sql: str, params: tuple = ()):
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchall()

    async def log(self, user_id: int, action: str, details: str = ""):
        try:
            await self.conn.execute(
                "INSERT INTO sys_logs(user_id, action, details) VALUES (?, ?, ?)",
                (user_id, action, details),
            )
            await self.conn.commit()
        except Exception:
            log.exception("Falha ao registrar log de auditoria")
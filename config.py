"""Configuração centralizada do Bot Unificado Colizeu."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Discord & Core ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/colizeu.db")
MOD_CHANNEL_ID = int(os.getenv("MOD_CHANNEL_ID", "0") or 0)
PERFIS_CHANNEL_ID = int(os.getenv("PERFIS_CHANNEL_ID", "0") or 0)
GUILD_ID = int(os.getenv("GUILD_ID", "0") or 0)

# --- YouTube ---
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_CHECK_MINUTES = int(os.getenv("YOUTUBE_CHECK_MINUTES", "5") or 5)

# --- Ofertas ---
OFFERS_CHECK_MINUTES = int(os.getenv("OFFERS_CHECK_MINUTES", "30") or 30)
MAX_OFFERS_PER_CHECK = int(os.getenv("MAX_OFFERS_PER_CHECK", "5") or 5)
MIN_PROMO_DISCOUNT = int(os.getenv("MIN_PROMO_DISCOUNT", "20") or 20)
GAMES_CHANNEL_ID = int(os.getenv("GAMES_CHANNEL_ID", "0") or 0)
PROMOS_CHANNEL_ID = int(os.getenv("PROMOS_CHANNEL_ID", "0") or 0)

# --- IA Suporte ---
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_RATE_LIMIT_PER_MIN = int(os.getenv("LLM_RATE_LIMIT_PER_MIN", "3") or 3)

# --- Gamificação ---
XP_ZERADO = int(os.getenv("XP_ZERADO", "50") or 50)
DENARIOS_ZERADO = int(os.getenv("DENARIOS_ZERADO", "10") or 10)
ZERADOS_XP_LIMITE_DIARIO = int(os.getenv("ZERADOS_XP_LIMITE_DIARIO", "5") or 5)

# --- Cores Padrão ---
COR_OURO = 0xFFD700
COR_PRATA = 0xC0C0C0

# --- Timezone ---
BRAZIL_TZ_NAME = "America/Sao_Paulo"

# Garante que o diretório de dados exista
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
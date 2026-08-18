# server.py (FastAPI)
import os
import sqlite3
import json
import hashlib
import hmac
import time
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# ==================== КОНФИГ ====================
BOT_TOKEN = "8707239993:AAEVh5E16a-lUyLzGov1fLIXvhV2IEAb788"
ADMIN_ID = 8814572765
DB_NAME = "arzdrop.db"
SKINS_DIR = "skins"

# ==================== ПРИЛОЖЕНИЕ ====================
app = FastAPI()

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Пользователи
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            register_date TIMESTAMP,
            balance INTEGER DEFAULT 500,
            daily_streak INTEGER DEFAULT 0,
            last_daily TIMESTAMP,
            total_opened INTEGER DEFAULT 0,
            xp INTEGER DEFAULT 0,
            is_banned BOOLEAN DEFAULT FALSE,
            is_admin BOOLEAN DEFAULT FALSE,
            steam_url TEXT,
            steam_id TEXT UNIQUE,
            group_id INTEGER,
            sub_arzdrop BOOLEAN DEFAULT FALSE,
            sub_artstudio BOOLEAN DEFAULT FALSE,
            last_top_notification INTEGER DEFAULT 0
        )
    ''')
    
    # Инвентарь
    cur.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            skin_id INTEGER REFERENCES skins(id),
            acquired_date TIMESTAMP,
            is_tradeable BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # Скины
    cur.execute('''
        CREATE TABLE IF NOT EXISTS skins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            weapon TEXT,
            rarity TEXT,
            wear TEXT,
            float_value REAL,
            price_rub INTEGER,
            price_usd REAL,
            collection TEXT
        )
    ''')
    
    # Кейсы
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price_open INTEGER,
            description TEXT
        )
    ''')
    
    # Связь кейс-скины
    cur.execute('''
        CREATE TABLE IF NOT EXISTS case_skins (
            case_id INTEGER REFERENCES cases(id),
            skin_id INTEGER REFERENCES skins(id),
            chance REAL,
            PRIMARY KEY (case_id, skin_id)
        )
    ''')
    
    # Промокоды
    cur.execute('''
        CREATE TABLE IF NOT EXISTS promocodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            reward INTEGER,
            uses_limit INTEGER,
            used_count INTEGER DEFAULT 0,
            expires_at TIMESTAMP,
            created_by INTEGER REFERENCES users(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS promocode_uses (
            user_id INTEGER REFERENCES users(id),
            promocode_id INTEGER REFERENCES promocodes(id),
            used_at TIMESTAMP,
            PRIMARY KEY (user_id, promocode_id)
        )
    ''')
    
    # Группы/кланы
    cur.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            tag TEXT,
            creator_id INTEGER REFERENCES users(id),
            max_members INTEGER DEFAULT 5,
            created_at TIMESTAMP,
            deleted BOOLEAN DEFAULT FALSE
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER REFERENCES groups(id),
            user_id INTEGER REFERENCES users(id),
            joined_at TIMESTAMP,
            role TEXT DEFAULT 'member',
            PRIMARY KEY (group_id, user_id)
        )
    ''')
    
    # Друзья
    cur.execute('''
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            friend_id INTEGER REFERENCES users(id),
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP,
            accepted_at TIMESTAMP
        )
    ''')
    
    # Заявки на вывод
    cur.execute('''
        CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            skin_id INTEGER REFERENCES skins(id),
            inventory_id INTEGER REFERENCES inventory(id),
            steam_url TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP,
            processed_at TIMESTAMP,
            admin_note TEXT
        )
    ''')
    
    # Настройки
    cur.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    conn.commit()
    
    # Создаём админа
    cur.execute('SELECT id FROM users WHERE id = ?', (ADMIN_ID,))
    if not cur.fetchone():
        cur.execute('''
            INSERT INTO users (id, first_name, register_date, last_daily, balance, is_admin)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (ADMIN_ID, "Admin", datetime.now(), datetime.now() - timedelta(days=1), 0, 1))
        conn.commit()
    
    # Заполняем кейсы и скины
    cur.execute("SELECT COUNT(*) FROM cases")
    if cur.fetchone()[0] == 0:
        # Кейс БОМЖ
        cur.execute('INSERT INTO cases (name, price_open, description) VALUES (?, ?, ?)',
                    ("БОМЖ", 500, "Кейс для бедных"))
        bomj_case = cur.lastrowid
        
        # Кейс DOLLAR
        cur.execute('INSERT INTO cases (name, price_open, description) VALUES (?, ?, ?)',
                    ("DOLLAR", 1500, "Кейс для богатых"))
        dollar_case = cur.lastrowid
        
        # Скины БОМЖ
        bomj_skins = [
            ("SCAR-20 Sand Mesh", "SCAR-20", "Базовое", "WW", 0.01, 3975, 0.03),
            ("UMP-45 Roadblock", "UMP-45", "Базовое", "BS", 0.04, 2312, 0.10),
            ("Five-SeveN Scrawl", "Five-SeveN", "Базовое", "FT", 0.07, 2040, 0.12),
            ("P250 Re.built", "P250", "Базовое", "BS", 0.08, 2012, 0.10),
            ("MAC-10 Monkeyflage", "MAC-10", "Базовое", "WW", 0.10, 1857, 0.10),
            ("Sticker Lynn Vision 2025", "Sticker", "Базовое", None, 0.15, 1672, 0.03),
            ("SCAR-20 Fragments", "SCAR-20", "Базовое", "FT", 0.17, 1607, 0.11),
            ("AUG Snake Pit", "AUG", "Базовое", "BS", 0.21, 1527, 0.08),
            ("Nova Dark Sigil", "Nova", "Базовое", "BS", 0.25, 1497, 0.10),
            ("Sticker Cxzi", "Sticker", "Базовое", None, 0.26, 1467, 0.03),
            ("Negev Ultralight", "Negev", "Базовое", "FT", 0.28, 1397, 0.11),
            ("Five-SeveN Scrawl", "Five-SeveN", "Базовое", "FT", 0.31, 1392, 0.09),
            ("Graffiti Bling", "Graffiti", "Базовое", None, 0.34, 1342, 0.03),
            ("P90 Freight", "P90", "Базовое", "BS", 0.34, 1325, 0.10),
            ("MP7 Forest DDPAT", "MP7", "Базовое", "MW", 0.34, 1300, 0.04),
            ("G3SG1 Polar Camo", "G3SG1", "Базовое", "MW", 0.40, 1252, 0.08),
            ("SSG 08 Blue Spruce", "SSG 08", "Базовое", "FT", 0.40, 1250, 0.05),
            ("Tec-9 Groundwater", "Tec-9", "Базовое", "FT", 0.42, 1162, 0.04),
            ("Galil AR Cold Fusion", "Galil AR", "Базовое", "BS", 0.45, 1137, 0.06),
            ("G3SG1 Jungle Dashed", "G3SG1", "Базовое", "FT", 0.48, 1100, 0.04),
            ("Galil AR VariCamo", "Galil AR", "Базовое", "MW", 0.49, 1065, 0.06),
            ("MP9 Slide", "MP9", "Базовое", "FT", 0.53, 1055, 0.06),
            ("M4A4 Mainframe", "M4A4", "Базовое", "BS", 0.55, 1020, 0.05),
            ("G3SG1 Desert Storm", "G3SG1", "Базовое", "FT", 0.55, 1000, 0.03),
            ("P90 Sand Spray", "P90", "Базовое", "FT", 0.55, 1000, 0.03),
            ("UMP-45 Mudder", "UMP-45", "Базовое", "WW", 0.55, 997, 0.04),
            ("Nova Mandrel", "Nova", "Базовое", "MW", 0.56, 992, 0.04),
            ("XM1014 Canvas Cloud", "XM1014", "Базовое", "FT", 0.58, 982, 0.03),
            ("MAG-7 Rust Coat", "MAG-7", "Базовое", "BS", 0.64, 977, 0.03),
            ("SG 553 Night Camo", "SG 553", "Базовое", "FT", 0.70, 922, 0.03),
            ("Nova Mandrel", "Nova", "Базовое", "FT", 0.70, 875, 0.03),
            ("Sticker apEX", "Sticker", "Базовое", None, 0.74, 852, 0.03),
            ("SCAR-20 Contractor", "SCAR-20", "Базовое", "BS", 0.79, 817, 0.03),
            ("MP5-SD Dirt Drop", "MP5-SD", "Базовое", "MW", 0.83, 790, 0.07),
            ("Sticker nafany", "Sticker", "Базовое", None, 0.84, 787, 0.04),
            ("Tec-9 Army Mesh", "Tec-9", "Базовое", "FT", 0.85, 780, 0.04),
            ("PP-Bizon Facility Sketch", "PP-Bizon", "Базовое", None, 0.85, 777, 0.04),
            ("Sticker malbsMd 2025", "Sticker", "Базовое", None, 0.90, 750, 0.03),
            ("Senzu Budapest", "Sticker", "Базовое", None, 0.91, 745, 0.03),
            ("PGL Antwerp'22", "Sticker", "Базовое", None, 0.92, 740, 0.03),
            ("Five-SeveN Coolant", "Five-SeveN", "Базовое", "FT", 0.92, 737, 0.04),
            ("Sticker n1ssim 2024", "Sticker", "Базовое", None, 0.92, 737, 0.03),
            ("G3SG1 Desert Storm", "G3SG1", "Базовое", "FT", 0.93, 730, 0.04),
            ("Five-SeveN Forest Night", "Five-SeveN", "Базовое", "FT", 0.96, 715, 0.04),
            ("UMP-45 Mudder", "UMP-45", "Базовое", "MW", 1.01, 710, 0.03),
            ("MAC-10 Bronzer", "MAC-10", "Базовое", "FT", 1.02, 690, 0.03),
            ("AUG Contractor", "AUG", "Базовое", "FT", 1.04, 685, 0.04),
            ("P250 Facility Draft", "P250", "Базовое", "FT", 1.04, 675, 0.04),
            ("Sticker Natus Vincere", "Sticker", "Базовое", None, 1.04, 675, 0.05),
            ("P90 Sand Spray", "P90", "Базовое", "BS", 1.04, 675, 0.03),
            ("Sticker JDG", "Sticker", "Базовое", None, 1.06, 670, 0.03),
            ("MP9 Sand Dashed", "MP9", "Базовое", "FT", 1.07, 662, 0.03),
            ("Sticker FURIA", "Sticker", "Базовое", None, 1.09, 665, 0.03),
            ("UMP-45 Facility Dark", "UMP-45", "Базовое", "FT", 1.09, 652, 0.03),
            ("Sticker Team Spirit", "Sticker", "Базовое", None, 1.09, 652, 0.06),
            ("SCAR-20 Contractor", "SCAR-20", "Базовое", "BS", 1.10, 650, 0.03),
            ("Tec-9 Blue Blast", "Tec-9", "Базовое", "MW", 1.11, 645, 0.03),
            ("Sticker hallzerk", "Sticker", "Базовое", None, 1.11, 642, 0.03),
            ("UMP-45 Facility Dark", "UMP-45", "Базовое", "FT", 1.15, 635, 0.03),
            ("MP5-SD Dirt Drop", "MP5-SD", "Базовое", "FT", 1.15, 622, 0.03),
            ("Nova Predator", "Nova", "Базовое", "FT", 1.24, 585, 0.03),
            ("Nova Sand Dune", "Nova", "Базовое", "FT", 1.25, 582, 0.04),
            ("MP9 Slide", "MP9", "Базовое", "FT", 1.28, 567, 0.03),
            ("Nova Sand Dune", "Nova", "Базовое", "BS", 1.48, 495, 0.03),
            ("Nova Polar Mesh", "Nova", "Базовое", "FT", 1.57, 465, 0.04),
            ("UMP-45 Green Swirl", "UMP-45", "Базовое", "FT", 3.05, 157, 0.03),
            ("SG 553 Night Camo", "SG 553", "Базовое", "FT", 3.05, 125, 0.03),
            ("Sticker FURIA", "Sticker", "Базовое", None, 3.05, 125, 0.03),
            ("SCAR-20 Zinc", "SCAR-20", "Базовое", "FT", 3.07, 125, 0.03),
            ("M249 Sage Camo", "M249", "Базовое", "FT", 3.07, 125, 0.03),
            ("MAG-7 Copper Oxide", "MAG-7", "Базовое", "FT", 3.05, 125, 0.03),
            ("FAMAS Palm", "FAMAS", "Базовое", "FT", 3.05, 125, 0.03),
            ("XM1014 Canvas Cloud", "XM1014", "Базовое", "FT", 3.05, 125, 0.03),
            ("MAC-10 Bronzer", "MAC-10", "Базовое", "FT", 3.05, 125, 0.03),
            ("AUG Commando Company", "AUG", "Базовое", "FT", 3.05, 125, 0.03),
            ("MP9 Buff Blue", "MP9", "Базовое", "FT", 3.05, 125, 0.03),
        ]
        
        for skin in bomj_skins:
            cur.execute('''
                INSERT INTO skins (name, weapon, rarity, wear, float_value, price_rub, price_usd, collection)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (skin[0], skin[1], skin[2], skin[3], skin[4], skin[5], skin[6], "БОМЖ"))
            skin_id = cur.lastrowid
            cur.execute('INSERT INTO case_skins (case_id, skin_id, chance) VALUES (?, ?, ?)',
                        (bomj_case, skin_id, skin[4]))
        
        # Скины DOLLAR
        dollar_skins = [
            ("Galil AR Control", "Galil AR", "Скрытое", "FT", 0.08, 10250, 0.62),
            ("SG 553 Dragon Tech", "SG 553", "Скрытое", "WW", 0.09, 10000, 0.64),
            ("MAG-7 Monster Call", "MAG-7", "Скрытое", "FT", 0.09, 9885, 0.66),
            ("SCAR-20 Assault", "SCAR-20", "Скрытое", "MW", 0.13, 8942, 0.59),
            ("P90 Off World", "P90", "Скрытое", "MW", 0.17, 8152, 0.54),
            ("P90 Grim", "P90", "Скрытое", "MW", 0.19, 7825, 0.57),
            ("R8 Revolver Crimson Web", "R8 Revolver", "Скрытое", "FT", 0.24, 7250, 0.48),
            ("MP5-SD Statics", "MP5-SD", "Скрытое", "FT", 0.45, 5482, 0.36),
            ("Charm Lil' No. 2", "Charm", "Скрытое", "MW", 0.46, 5407, 0.38),
            ("FAMAS Teardown", "FAMAS", "Скрытое", "MW", 0.46, 5382, 0.39),
            ("Sticker Clown Nose", "Sticker", "Скрытое", None, 0.56, 5000, 0.36),
            ("R8 Revolver Junk Yard", "R8 Revolver", "Скрытое", "FT", 0.56, 4852, 0.31),
            ("SG 553 Aloha", "SG 553", "Скрытое", "MW", 0.63, 4540, 0.29),
            ("G3SG1 Green Apple", "G3SG1", "Скрытое", "FN", 0.66, 4385, 0.34),
            ("Galil AR Cold Fusion", "Galil AR", "Скрытое", "MW", 0.84, 3747, 0.30),
            ("Five-SeveN Scrawl", "Five-SeveN", "Скрытое", "MW", 0.90, 3555, 0.27),
            ("MAC-10 Candy Apple", "MAC-10", "Скрытое", "FT", 0.90, 3527, 0.29),
            ("G3SG1 Polar Camo", "G3SG1", "Скрытое", "FT", 0.98, 3297, 0.04),
            ("AUG Triqua", "AUG", "Скрытое", "STATTRAK™/FT", 1.28, 3290, 0.23),
            ("MP9 Black Sand", "MP9", "Скрытое", "MW", 1.32, 2630, 0.13),
            ("MAC-10 Light Box", "MAC-10", "Скрытое", "FT", 1.35, 2572, 0.15),
            ("M4A1-S Wash me plz", "M4A1-S", "Скрытое", "FT", 1.47, 2470, 0.15),
            ("USP-S PC-GRN", "USP-S", "Скрытое", "FT", 1.47, 2415, 0.15),
            ("P250 Cassette", "P250", "Скрытое", "FT", 1.47, 2180, 0.14),
            ("MP7 Motherboard", "MP7", "Скрытое", "FT", 1.57, 1997, 0.05),
            ("P2000 Granite Marbleized", "P2000", "Скрытое", "MW", 1.66, 1862, 0.13),
            ("Negev Bulkhead", "Negev", "Скрытое", "MW", 1.66, 1850, 0.13),
            ("Galil AR Green Apple", "Galil AR", "Скрытое", "MW", 1.67, 1830, 0.11),
            ("Five-SeveN Scrawl", "Five-SeveN", "Скрытое", "WW", 1.67, 1835, 0.10),
            ("MP7 Motherboard", "MP7", "Скрытое", "MW", 1.74, 1720, 0.14),
            ("Motherboard", "MP7", "Скрытое", "FT", 1.78, 1720, 0.14),
            ("SG 553 Basket Halftone", "SG 553", "Скрытое", "MW", 1.78, 1647, 0.08),
            ("MP5-SD Liquidation", "MP5-SD", "Скрытое", "STATTRAK™/WW", 1.78, 1655, 0.11),
            ("Zeus x27 Electric Blue", "Zeus x27", "Скрытое", "MW", 1.79, 1642, 0.13),
            ("P250 Cassette", "P250", "Скрытое", "BS", 1.81, 1605, 0.14),
            ("P250 Sleet", "P250", "Скрытое", "FN", 1.88, 1497, 0.08),
            ("SG 553 Ol' Rusty", "SG 553", "Скрытое", "WW", 1.92, 1440, 0.12),
            ("M4A4 Naval Shred Camo", "M4A4", "Скрытое", "FT", 2.07, 1227, 0.05),
            ("SSG 08 Blue Spruce", "SSG 08", "Скрытое", "MW", 2.08, 1225, 0.05),
            ("Dual Berettas Hideout", "Dual Berettas", "Скрытое", "FT", 2.08, 1215, 0.11),
            ("AUG Condemned", "AUG", "Скрытое", "FT", 2.08, 1212, 0.06),
            ("Five-SeveN Sky Blue", "Five-SeveN", "Скрытое", "MW", 2.16, 1117, 0.11),
            ("Galil AR Cold Fusion", "Galil AR", "Скрытое", "FT", 2.19, 1075, 0.06),
            ("Nova Mandrel", "Nova", "Скрытое", "MW", 2.26, 990, 0.04),
            ("UMP-45 Mudder", "UMP-45", "Скрытое", "BS", 2.27, 975, 0.03),
            ("PP-Bizon Night Ops", "PP-Bizon", "Скрытое", "FT", 2.28, 967, 0.05),
            ("PP-Bizon Cold Cell", "PP-Bizon", "Скрытое", "MW", 2.37, 855, 0.07),
            ("G3SG1 Red Jasper", "G3SG1", "Скрытое", "FN", 2.38, 847, 0.06),
            ("MP7 Army Recon", "MP7", "Скрытое", "MW", 2.41, 812, 0.05),
            ("Sticker huNTER", "Sticker", "Скрытое", None, 2.46, 750, 0.03),
            ("Sticker Virtus.Pro", "Sticker", "Скрытое", None, 2.54, 447, 0.04),
            ("MP9 Sand Dashed", "MP9", "Скрытое", "FT", 2.56, 665, 0.03),
            ("SCAR-20 Sand Mesh", "SCAR-20", "Скрытое", "BS", 2.57, 640, 0.03),
            ("Sticker Retro Zeus", "Sticker", "Скрытое", None, 2.57, 630, 0.03),
            ("Tec-9 Urban DDPAT", "Tec-9", "Скрытое", "FT", 2.61, 595, 0.05),
            ("M4A4 Aeolian Dark", "M4A4", "Скрытое", "FT", 2.81, 382, 0.03),
            ("Zeus x27 Swamp DDPAT", "Zeus x27", "Скрытое", "MW", 3.01, 200, 0.03),
            ("MAC-10 Storm Camo", "MAC-10", "Скрытое", "MW", 3.09, 125, 0.03),
            ("MP5-SD Lime Hex", "MP5-SD", "Скрытое", "MW", 3.09, 125, 0.03),
            ("MP9 Dizzy", "MP9", "Скрытое", "WW", 3.09, 125, 0.03),
        ]
        
        for skin in dollar_skins:
            cur.execute('''
                INSERT INTO skins (name, weapon, rarity, wear, float_value, price_rub, price_usd, collection)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (skin[0], skin[1], skin[2], skin[3], skin[4], skin[5], skin[6], "DOLLAR"))
            skin_id = cur.lastrowid
            cur.execute('INSERT INTO case_skins (case_id, skin_id, chance) VALUES (?, ?, ?)',
                        (dollar_case, skin_id, skin[4]))
        
        conn.commit()
    
    conn.close()

# ==================== МОДЕЛИ ДАННЫХ ====================
class AuthData(BaseModel):
    init_data: str

class OpenCaseRequest(BaseModel):
    case_name: str

class UpgradeRequest(BaseModel):
    inventory_id: int
    target_skin_id: int

# ==================== ЗАЩИТА ====================
def verify_telegram_auth(init_data: str) -> Optional[int]:
    """Проверяет подпись Telegram WebApp и возвращает user_id"""
    try:
        params = dict(x.split('=') for x in init_data.split('&'))
        hash_value = params.pop('hash', None)
        if not hash_value:
            return None
        
        # Сортируем ключи
        data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(params.items()))
        
        # Вычисляем подпись
        secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if computed_hash != hash_value:
            return None
        
        # Проверяем время (актуально 24 часа)
        auth_date = int(params.get('auth_date', 0))
        if time.time() - auth_date > 86400:
            return None
        
        # Извлекаем user_id
        user_data = json.loads(params.get('user', '{}'))
        return user_data.get('id')
    except:
        return None

# ==================== ЛИМИТЫ ====================
limits = {
    'cases': {},
    'upgrades': {}
}

def check_limit(user_id: int, action: str, max_per_minute: int) -> bool:
    now = time.time()
    timestamps = limits[action].get(user_id, [])
    timestamps = [t for t in timestamps if now - t < 60]
    if len(timestamps) >= max_per_minute:
        return False
    timestamps.append(now)
    limits[action][user_id] = timestamps
    return True

# ==================== РАБОТА С БД ====================
def get_db():
    return sqlite3.connect(DB_NAME)

def get_user(user_id: int) -> Optional[Dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        columns = ['id', 'username', 'first_name', 'register_date', 'balance', 'daily_streak',
                   'last_daily', 'total_opened', 'xp', 'is_banned', 'is_admin',
                   'steam_url', 'steam_id', 'group_id', 'sub_arzdrop', 'sub_artstudio',
                   'last_top_notification']
        return dict(zip(columns, row))
    return None

def create_user(user_id: int, first_name: str = None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id FROM users WHERE id = ?', (user_id,))
    if cur.fetchone():
        conn.close()
        return
    
    is_admin = 1 if user_id == ADMIN_ID else 0
    cur.execute('''
        INSERT INTO users (id, first_name, register_date, last_daily, balance, is_admin)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, first_name, datetime.now(), datetime.now() - timedelta(days=1), 500, is_admin))
    conn.commit()
    conn.close()

def get_balance(user_id: int) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT balance FROM users WHERE id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0

def update_balance(user_id: int, amount: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE users SET balance = balance + ? WHERE id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_inventory(user_id: int) -> List[Dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT s.*, i.id as inv_id, i.acquired_date
        FROM inventory i
        JOIN skins s ON i.skin_id = s.id
        WHERE i.user_id = ?
        ORDER BY i.acquired_date DESC
    ''', (user_id,))
    rows = cur.fetchall()
    conn.close()
    columns = ['id', 'name', 'weapon', 'rarity', 'wear', 'float_value', 'price_rub',
               'price_usd', 'collection', 'inv_id', 'acquired_date']
    return [dict(zip(columns, row)) for row in rows]

def get_skin(skin_id: int) -> Optional[Dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM skins WHERE id = ?', (skin_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        columns = ['id', 'name', 'weapon', 'rarity', 'wear', 'float_value', 'price_rub', 'price_usd', 'collection']
        return dict(zip(columns, row))
    return None

def get_case_skins(case_name: str) -> List[Dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT s.*, cs.chance
        FROM case_skins cs
        JOIN skins s ON cs.skin_id = s.id
        JOIN cases c ON cs.case_id = c.id
        WHERE c.name = ?
    ''', (case_name,))
    rows = cur.fetchall()
    conn.close()
    columns = ['id', 'name', 'weapon', 'rarity', 'wear', 'float_value', 'price_rub',
               'price_usd', 'collection', 'chance']
    return [dict(zip(columns, row)) for row in rows]

def get_case_price(case_name: str) -> Optional[int]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT price_open FROM cases WHERE name = ?', (case_name,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def open_case(user_id: int, case_name: str) -> Optional[Dict]:
    conn = get_db()
    cur = conn.cursor()
    
    # Проверяем баланс
    balance = get_balance(user_id)
    price = get_case_price(case_name)
    if not price or balance < price:
        conn.close()
        return None
    
    # Списываем деньги
    update_balance(user_id, -price)
    
    # Получаем скины из кейса
    skins = get_case_skins(case_name)
    if not skins:
        conn.close()
        return None
    
    # Выбираем скин по шансу
    weights = [s['chance'] for s in skins]
    selected = random.choices(skins, weights=weights, k=1)[0]
    
    # Добавляем в инвентарь
    cur.execute('INSERT INTO inventory (user_id, skin_id, acquired_date) VALUES (?, ?, ?)',
                (user_id, selected['id'], datetime.now()))
    cur.execute('UPDATE users SET total_opened = total_opened + 1, xp = xp + 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    return selected

def do_upgrade(user_id: int, inventory_id: int, target_skin_id: int) -> Dict:
    conn = get_db()
    cur = conn.cursor()
    
    # Проверяем, что скин в инвентаре у пользователя
    cur.execute('SELECT id, skin_id FROM inventory WHERE id = ? AND user_id = ?', (inventory_id, user_id))
    inv = cur.fetchone()
    if not inv:
        conn.close()
        return {'success': False, 'error': 'Скин не найден'}
    
    inv_id, current_skin_id = inv
    
    # Получаем текущий скин
    current = get_skin(current_skin_id)
    target = get_skin(target_skin_id)
    
    if not current or not target:
        conn.close()
        return {'success': False, 'error': 'Скин не найден'}
    
    # Проверяем условия апгрейда
    in_price = current['price_rub']
    out_price = target['price_rub']
    
    if in_price < 1000:
        conn.close()
        return {'success': False, 'error': 'Цена входа должна быть ≥ 1000 монет'}
    
    if out_price <= in_price or out_price > in_price * 8:
        conn.close()
        return {'success': False, 'error': 'Недопустимая цена выхода'}
    
    # Вычисляем шанс
    raw_chance = (in_price / out_price) * 0.9 * 100
    chance = max(0.1, min(95, raw_chance))
    
    # Удаляем входной скин
    cur.execute('DELETE FROM inventory WHERE id = ?', (inv_id,))
    
    # Роллим
    success = random.random() * 100 < chance
    
    if success:
        # Добавляем целевой скин
        cur.execute('INSERT INTO inventory (user_id, skin_id, acquired_date) VALUES (?, ?, ?)',
                    (user_id, target_skin_id, datetime.now()))
        conn.commit()
        conn.close()
        return {
            'success': True,
            'chance': chance,
            'result': 'win',
            'skin': target
        }
    else:
        conn.commit()
        conn.close()
        return {
            'success': True,
            'chance': chance,
            'result': 'lose',
            'skin': target
        }

# ==================== API РУЧКИ ====================
@app.post("/api/auth")
async def auth(data: AuthData):
    user_id = verify_telegram_auth(data.init_data)
    if not user_id:
        raise HTTPException(status_code=403, detail="Invalid auth")
    
    # Создаём пользователя если его нет
    create_user(user_id)
    
    return {"user_id": user_id}

@app.get("/api/profile/{user_id}")
async def profile(user_id: int):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/api/inventory/{user_id}")
async def inventory(user_id: int):
    return get_inventory(user_id)

@app.post("/api/open_case")
async def open_case_api(req: OpenCaseRequest, request: Request):
    # Проверяем авторизацию через заголовок
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user_id = int(user_id)
    
    # Проверяем лимиты
    if not check_limit(user_id, 'cases', 20):
        raise HTTPException(status_code=429, detail="Too many cases (max 20 per minute)")
    
    # Открываем кейс
    result = open_case(user_id, req.case_name)
    if not result:
        raise HTTPException(status_code=400, detail="Недостаточно монет или кейс не найден")
    
    return result

@app.post("/api/upgrade")
async def upgrade_api(req: UpgradeRequest, request: Request):
    # Проверяем авторизацию
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user_id = int(user_id)
    
    # Проверяем лимиты
    if not check_limit(user_id, 'upgrades', 5):
        raise HTTPException(status_code=429, detail="Too many upgrades (max 5 per minute)")
    
    # Выполняем апгрейд
    result = do_upgrade(user_id, req.inventory_id, req.target_skin_id)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result.get('error', 'Ошибка'))
    
    return result

@app.get("/api/skins/{skin_id}")
async def get_skin_image(skin_id: int):
    """Отдаёт картинку скина из папки skins/"""
    img_path = f"{SKINS_DIR}/{skin_id}.jpg"
    if os.path.exists(img_path):
        return FileResponse(img_path)
    # Если нет картинки — отдаём заглушку
    default_path = f"{SKINS_DIR}/default.jpg"
    if os.path.exists(default_path):
        return FileResponse(default_path)
    # Если нет даже заглушки — возвращаем 404
    raise HTTPException(status_code=404, detail="Image not found")

@app.get("/api/top_players")
async def top_players():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, first_name, balance, total_opened
        FROM users
        WHERE is_banned = FALSE AND id != ? AND is_admin = FALSE
        ORDER BY balance DESC
        LIMIT 10
    ''', (ADMIN_ID,))
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'name': r[1], 'balance': r[2], 'opened': r[3]} for r in rows]

@app.get("/api/top_clans")
async def top_clans():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT g.name, g.tag, COUNT(gm.user_id) as members,
               COALESCE(AVG(u.balance), 0) as avg_balance
        FROM groups g
        LEFT JOIN group_members gm ON g.id = gm.group_id
        LEFT JOIN users u ON gm.user_id = u.id
        WHERE g.deleted = FALSE
        GROUP BY g.id
        HAVING members > 0
        ORDER BY avg_balance DESC
        LIMIT 10
    ''')
    rows = cur.fetchall()
    conn.close()
    return [{'name': r[0], 'tag': r[1], 'members': r[2], 'avg_balance': int(r[3])} for r in rows]

@app.get("/")
async def root():
    return {"status": "ARZDROP API", "version": "1.0"}

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    init_db()
    print("🚀 Сервер ARZDROP запущен на http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)

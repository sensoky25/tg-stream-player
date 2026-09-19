"""
SQLite Database Layer for Telegram Mini App Drama/Movie Management.
Handles series, movies, episodes, and media associations.
"""

import sqlite3
import os
from pathlib import Path
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import config

DB_PATH = Path(__file__).parent / "dramas.db"

def get_db_connection() -> sqlite3.Connection:
    """Create and return a SQLite database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initialize database tables if they do not exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Series / Movies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                original_title TEXT DEFAULT '',
                type TEXT NOT NULL DEFAULT 'series', -- 'series' or 'movie'
                poster_url TEXT DEFAULT '',
                backdrop_url TEXT DEFAULT '',
                description TEXT DEFAULT '',
                genres TEXT DEFAULT '', -- Comma-separated (e.g. 'រឿងភាគកូរ៉េ, សកម្មភាព, មនោសញ្ចេតនា')
                status TEXT DEFAULT 'ongoing', -- 'ongoing' or 'completed'
                release_year TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Episodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id INTEGER NOT NULL,
                episode_num REAL NOT NULL,
                title TEXT DEFAULT '',
                msg_id INTEGER,
                stream_url TEXT DEFAULT '',
                file_name TEXT DEFAULT '',
                file_size INTEGER DEFAULT 0,
                duration INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (series_id) REFERENCES series (id) ON DELETE CASCADE
            );
        """)

        # Recent Uploads table (Tracks media forwarded to bot for 1-click episode assignment)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recent_uploads (
                msg_id INTEGER PRIMARY KEY,
                file_name TEXT DEFAULT '',
                file_size INTEGER DEFAULT 0,
                mime_type TEXT DEFAULT '',
                stream_url TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Settings table (Key-Value configuration for hotlink protection and system flags)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Indexes for fast search and ordering
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_series_title ON series (title);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_series_type ON series (type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodes_series ON episodes (series_id, episode_num);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recent_created ON recent_uploads (created_at);")

        conn.commit()

# ========================================================
# Series Operations
# ========================================================

def get_all_series(
    search: Optional[str] = None,
    genre: Optional[str] = None,
    series_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Retrieve series with optional filters, search, and episode count."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = """
            SELECT 
                s.*,
                COUNT(e.id) AS episode_count,
                MAX(e.episode_num) AS latest_episode
            FROM series s
            LEFT JOIN episodes e ON s.id = e.series_id
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND (s.title LIKE ? OR s.original_title LIKE ? OR s.description LIKE ?)"
            term = f"%{search.strip()}%"
            params.extend([term, term, term])

        if genre and genre != "all":
            query += " AND s.genres LIKE ?"
            params.append(f"%{genre.strip()}%")

        if series_type and series_type != "all":
            query += " AND s.type = ?"
            params.append(series_type.strip())

        if status and status != "all":
            query += " AND s.status = ?"
            params.append(status.strip())

        query += " GROUP BY s.id ORDER BY s.updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_series_by_id(series_id: int) -> Optional[Dict[str, Any]]:
    """Get single series details along with all its episodes."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                s.*,
                COUNT(e.id) AS episode_count,
                MAX(e.episode_num) AS latest_episode
            FROM series s
            LEFT JOIN episodes e ON s.id = e.series_id
            WHERE s.id = ?
            GROUP BY s.id
        """, (series_id,))
        
        series_row = cursor.fetchone()
        if not series_row:
            return None
        
        series = dict(series_row)

        cursor.execute("""
            SELECT * FROM episodes 
            WHERE series_id = ? 
            ORDER BY episode_num ASC, id ASC
        """, (series_id,))
        episodes = [dict(row) for row in cursor.fetchall()]
        series["episodes"] = episodes

        return series

def create_series(data: Dict[str, Any]) -> int:
    """Insert a new drama or movie."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO series (
                title, original_title, type, poster_url, backdrop_url,
                description, genres, status, release_year, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            data.get("title", "").strip(),
            data.get("original_title", "").strip(),
            data.get("type", "series").strip(),
            data.get("poster_url", "").strip(),
            data.get("backdrop_url", "").strip(),
            data.get("description", "").strip(),
            data.get("genres", "").strip(),
            data.get("status", "ongoing").strip(),
            data.get("release_year", "").strip(),
        ))
        conn.commit()
        return cursor.lastrowid

def update_series(series_id: int, data: Dict[str, Any]) -> bool:
    """Update an existing series."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE series SET
                title = COALESCE(?, title),
                original_title = COALESCE(?, original_title),
                type = COALESCE(?, type),
                poster_url = COALESCE(?, poster_url),
                backdrop_url = COALESCE(?, backdrop_url),
                description = COALESCE(?, description),
                genres = COALESCE(?, genres),
                status = COALESCE(?, status),
                release_year = COALESCE(?, release_year),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            data.get("title"),
            data.get("original_title"),
            data.get("type"),
            data.get("poster_url"),
            data.get("backdrop_url"),
            data.get("description"),
            data.get("genres"),
            data.get("status"),
            data.get("release_year"),
            series_id
        ))
        conn.commit()
        return cursor.rowcount > 0

def delete_series(series_id: int) -> bool:
    """Delete a series and its associated episodes."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM series WHERE id = ?", (series_id,))
        conn.commit()
        return cursor.rowcount > 0

# ========================================================
# Episode Operations
# ========================================================

def add_episode(series_id: int, data: Dict[str, Any]) -> int:
    """Add an episode to a series."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Determine next episode number if not provided
        ep_num = data.get("episode_num")
        if ep_num is None or ep_num == "":
            cursor.execute("SELECT COALESCE(MAX(episode_num), 0) + 1 FROM episodes WHERE series_id = ?", (series_id,))
            ep_num = cursor.fetchone()[0]

        title = data.get("title")
        if not title:
            title = f"ភាគ {int(float(ep_num)) if float(ep_num).is_integer() else ep_num}"

        cursor.execute("""
            INSERT INTO episodes (
                series_id, episode_num, title, msg_id, stream_url, file_name, file_size, duration
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            series_id,
            float(ep_num),
            title.strip(),
            data.get("msg_id"),
            data.get("stream_url", "").strip(),
            data.get("file_name", "").strip(),
            int(data.get("file_size", 0) or 0),
            int(data.get("duration", 0) or 0)
        ))
        
        # Touch series updated_at
        cursor.execute("UPDATE series SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (series_id,))
        conn.commit()
        return cursor.lastrowid

def update_episode(episode_id: int, data: Dict[str, Any]) -> bool:
    """Update an episode."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE episodes SET
                episode_num = COALESCE(?, episode_num),
                title = COALESCE(?, title),
                msg_id = COALESCE(?, msg_id),
                stream_url = COALESCE(?, stream_url),
                file_name = COALESCE(?, file_name),
                file_size = COALESCE(?, file_size),
                duration = COALESCE(?, duration)
            WHERE id = ?
        """, (
            data.get("episode_num"),
            data.get("title"),
            data.get("msg_id"),
            data.get("stream_url"),
            data.get("file_name"),
            data.get("file_size"),
            data.get("duration"),
            episode_id
        ))
        
        # Touch parent series updated_at
        cursor.execute("""
            UPDATE series SET updated_at = CURRENT_TIMESTAMP 
            WHERE id = (SELECT series_id FROM episodes WHERE id = ?)
        """, (episode_id,))
        conn.commit()
        return cursor.rowcount > 0

def delete_episode(episode_id: int) -> bool:
    """Delete an episode."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Touch parent series updated_at before deleting
        cursor.execute("""
            UPDATE series SET updated_at = CURRENT_TIMESTAMP 
            WHERE id = (SELECT series_id FROM episodes WHERE id = ?)
        """, (episode_id,))
        cursor.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_stats() -> Dict[str, Any]:
    """Get total series, episodes, and media size summary."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM series")
        total_series = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM series WHERE type = 'series'")
        drama_series_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM series WHERE type = 'movie'")
        movie_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM episodes")
        ep_row = cursor.fetchone()
        total_episodes = ep_row[0]
        total_bytes = ep_row[1]

        return {
            "total_series": total_series,
            "drama_series_count": drama_series_count,
            "movie_count": movie_count,
            "total_episodes": total_episodes,
            "total_bytes": total_bytes
        }

# ========================================================
# Recent Uploads Operations
# ========================================================

def save_recent_upload(msg_id: int, file_name: str, file_size: int, mime_type: str, stream_url: str):
    """Save or update a recently forwarded media item."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO recent_uploads (msg_id, file_name, file_size, mime_type, stream_url, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(msg_id) DO UPDATE SET
                file_name = excluded.file_name,
                file_size = excluded.file_size,
                mime_type = excluded.mime_type,
                stream_url = excluded.stream_url,
                created_at = CURRENT_TIMESTAMP
        """, (msg_id, file_name, file_size, mime_type, stream_url))
        conn.commit()

def get_recent_uploads(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve the most recently uploaded media items."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT msg_id as id, file_name, file_size, mime_type, stream_url, created_at as date
            FROM recent_uploads
            ORDER BY created_at DESC, msg_id DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

# ========================================================
# System & Security Settings Operations
# ========================================================

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve a single setting value by key."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row["value"]
        return default

def set_setting(key: str, value: str):
    """Store or update a setting value."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key, str(value)))
        conn.commit()

def get_security_settings() -> Dict[str, Any]:
    """
    Retrieve security/hotlink protection settings.
    Falls back to config.py/.env if not set in database.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings WHERE key IN ('hotlink_protection_enabled', 'allowed_domains', 'allow_empty_referer')")
        rows = dict(cursor.fetchall())

    if "hotlink_protection_enabled" in rows:
        hotlink_enabled = rows["hotlink_protection_enabled"] in ("1", "true", "True")
    else:
        hotlink_enabled = config.HOTLINK_PROTECTION

    if "allow_empty_referer" in rows:
        allow_empty_referer = rows["allow_empty_referer"] in ("1", "true", "True")
    else:
        allow_empty_referer = config.ALLOW_EMPTY_REFERER

    if "allowed_domains" in rows:
        try:
            allowed_domains = json.loads(rows["allowed_domains"])
            if not isinstance(allowed_domains, list):
                allowed_domains = []
        except Exception:
            raw = rows["allowed_domains"]
            allowed_domains = [d.strip().lower() for d in raw.split(",") if d.strip()]
    else:
        allowed_domains = list(config.ALLOWED_DOMAINS)

    return {
        "hotlink_protection_enabled": bool(hotlink_enabled),
        "allowed_domains": allowed_domains,
        "allow_empty_referer": bool(allow_empty_referer)
    }

def update_security_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update security/hotlink settings in database."""
    if "hotlink_protection_enabled" in data:
        val = "1" if data["hotlink_protection_enabled"] else "0"
        set_setting("hotlink_protection_enabled", val)

    if "allow_empty_referer" in data:
        val = "1" if data["allow_empty_referer"] else "0"
        set_setting("allow_empty_referer", val)

    if "allowed_domains" in data:
        domains = data["allowed_domains"]
        if isinstance(domains, list):
            cleaned = []
            for d in domains:
                d_str = str(d).strip().lower()
                # Remove protocols or slashes if user typed http://example.com/
                if "://" in d_str:
                    d_str = d_str.split("://", 1)[1]
                d_str = d_str.split("/", 1)[0].strip()
                if d_str and d_str not in cleaned:
                    cleaned.append(d_str)
            set_setting("allowed_domains", json.dumps(cleaned))
        elif isinstance(domains, str):
            cleaned = []
            for d in domains.split(","):
                d_str = d.strip().lower()
                if "://" in d_str:
                    d_str = d_str.split("://", 1)[1]
                d_str = d_str.split("/", 1)[0].strip()
                if d_str and d_str not in cleaned:
                    cleaned.append(d_str)
            set_setting("allowed_domains", json.dumps(cleaned))

    return get_security_settings()

# Initialize on module import
init_db()

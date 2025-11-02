"""
База данных для хранения метаданных файлов и транскриптов
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from app.config import get_config


class Database:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = get_config().database.db_path
        
        self.db_path = db_path
        self.conn = None
        self._init_db()
    
    def _init_db(self):
        """Инициализация базы данных"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # Создаем таблицы
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                filepath TEXT UNIQUE NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                status TEXT DEFAULT 'pending',
                error_message TEXT
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                transcript_path TEXT NOT NULL,
                text_preview TEXT,
                word_count INTEGER,
                duration_seconds REAL,
                language TEXT,
                model_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transcript_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                chunk_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
            )
        """)
        
        # Создаем индексы
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_files_status ON files(status)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_file_id ON transcripts(file_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_transcript_id ON chunks(transcript_id)")
        
        # Full-text search для транскриптов
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts 
            USING fts5(text_preview, content='transcripts', content_rowid='id')
        """)
        
        self.conn.commit()
    
    def add_file(self, filename: str, filepath: str, file_type: str, file_size: int) -> int:
        """Добавить файл в базу"""
        cursor = self.conn.execute("""
            INSERT INTO files (filename, filepath, file_type, file_size)
            VALUES (?, ?, ?, ?)
        """, (filename, filepath, file_type, file_size))
        self.conn.commit()
        return cursor.lastrowid
    
    def update_file_status(self, file_id: int, status: str, error_message: Optional[str] = None):
        """Обновить статус файла"""
        self.conn.execute("""
            UPDATE files 
            SET status = ?, 
                error_message = ?,
                processed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, error_message, file_id))
        self.conn.commit()
    
    def add_transcript(self, file_id: int, transcript_path: str, text_preview: str,
                      word_count: int, duration_seconds: float, language: str, model_used: str) -> int:
        """Добавить транскрипт"""
        cursor = self.conn.execute("""
            INSERT INTO transcripts 
            (file_id, transcript_path, text_preview, word_count, duration_seconds, language, model_used)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (file_id, transcript_path, text_preview, word_count, duration_seconds, language, model_used))
        
        # Добавляем в FTS индекс
        transcript_id = cursor.lastrowid
        self.conn.execute("""
            INSERT INTO transcripts_fts(rowid, text_preview)
            VALUES (?, ?)
        """, (transcript_id, text_preview))
        
        self.conn.commit()
        return transcript_id
    
    def add_chunks(self, transcript_id: int, chunks: List[str]):
        """Добавить чанки текста"""
        for i, chunk_text in enumerate(chunks):
            self.conn.execute("""
                INSERT INTO chunks (transcript_id, chunk_index, chunk_text, chunk_size)
                VALUES (?, ?, ?, ?)
            """, (transcript_id, i, chunk_text, len(chunk_text)))
        self.conn.commit()
    
    def search_transcripts(self, query: str, limit: int = 10) -> List[Dict]:
        """Поиск по транскриптам (full-text search)"""
        cursor = self.conn.execute("""
            SELECT 
                t.id,
                t.text_preview,
                t.transcript_path,
                f.filename,
                f.filepath,
                t.created_at
            FROM transcripts_fts fts
            JOIN transcripts t ON t.id = fts.rowid
            JOIN files f ON f.id = t.file_id
            WHERE transcripts_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_all_files(self, status: Optional[str] = None) -> List[Dict]:
        """Получить список всех файлов"""
        if status:
            cursor = self.conn.execute("""
                SELECT * FROM files WHERE status = ? ORDER BY created_at DESC
            """, (status,))
        else:
            cursor = self.conn.execute("""
                SELECT * FROM files ORDER BY created_at DESC
            """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_file_by_id(self, file_id: int) -> Optional[Dict]:
        """Получить файл по ID"""
        cursor = self.conn.execute("SELECT * FROM files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_transcript_by_file_id(self, file_id: int) -> Optional[Dict]:
        """Получить транскрипт по ID файла"""
        cursor = self.conn.execute("""
            SELECT * FROM transcripts WHERE file_id = ? ORDER BY created_at DESC LIMIT 1
        """, (file_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_chunks_by_transcript_id(self, transcript_id: int) -> List[Dict]:
        """Получить все чанки транскрипта"""
        cursor = self.conn.execute("""
            SELECT * FROM chunks WHERE transcript_id = ? ORDER BY chunk_index
        """, (transcript_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_file(self, file_id: int):
        """Удалить файл и связанные данные (каскадное удаление)"""
        self.conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        self.conn.commit()
    
    def get_stats(self) -> Dict:
        """Получить статистику"""
        stats = {}
        
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM files")
        stats['total_files'] = cursor.fetchone()['count']
        
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM files WHERE status = 'completed'")
        stats['processed_files'] = cursor.fetchone()['count']
        
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM transcripts")
        stats['total_transcripts'] = cursor.fetchone()['count']
        
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM chunks")
        stats['total_chunks'] = cursor.fetchone()['count']
        
        cursor = self.conn.execute("SELECT SUM(file_size) as total FROM files")
        total_size = cursor.fetchone()['total']
        stats['total_size_mb'] = round(total_size / 1024 / 1024, 2) if total_size else 0
        
        return stats
    
    def close(self):
        """Закрыть соединение с базой"""
        if self.conn:
            self.conn.close()


if __name__ == "__main__":
    # Тест базы данных
    db = Database("./data/test.db")
    
    # Добавляем тестовый файл
    file_id = db.add_file("test.mp3", "/path/to/test.mp3", "audio", 1024000)
    print(f"Created file with id: {file_id}")
    
    # Обновляем статус
    db.update_file_status(file_id, "processing")
    
    # Добавляем транскрипт
    transcript_id = db.add_transcript(
        file_id=file_id,
        transcript_path="/path/to/transcript.txt",
        text_preview="Это тестовый транскрипт файла",
        word_count=100,
        duration_seconds=120.5,
        language="ru",
        model_used="large-v3"
    )
    print(f"Created transcript with id: {transcript_id}")
    
    # Добавляем чанки
    db.add_chunks(transcript_id, ["Чанк 1", "Чанк 2", "Чанк 3"])
    
    # Получаем статистику
    stats = db.get_stats()
    print(f"\nStats: {stats}")
    
    # Поиск
    results = db.search_transcripts("тестовый")
    print(f"\nSearch results: {len(results)}")
    
    db.close()
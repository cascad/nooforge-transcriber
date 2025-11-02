# config.py
"""
Конфигурация Whisper RAG Studio (+ NooForge-Refiner settings)
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class TranscriberConfig:
    """Настройки транскрибатора"""
    use_faster_whisper: bool = True
    model_name: str = "large-v3"
    model_path: Optional[str] = None
    device: str = "cuda"  # cuda / cpu
    compute_type: str = "float16"  # float16 / int8 / float32
    language: str = "ru"

    # VAD настройки
    use_vad: bool = True
    vad_threshold: float = 0.5

    # Фильтрация галлюцинаций
    filter_hallucinations: bool = True
    hallucinations: list = field(default_factory=lambda: [
        "продолжение следует",
        "субтитры создавал",
        "спасибо за просмотр",
        "подпишитесь на канал",
        "ставьте лайки"
    ])


@dataclass
class ChunkerConfig:
    """Настройки нарезки текста"""
    chunk_size: int = 1000  # символов
    chunk_overlap: int = 200  # символов перекрытия
    separator: str = "\n\n"  # разделитель


@dataclass
class DatabaseConfig:
    """Настройки базы данных"""
    db_path: str = "./data/database.db"
    transcripts_dir: str = "./data/transcripts"
    chunks_dir: str = "./data/chunks"


@dataclass
class APIConfig:
    """Локальный REST API (если он у тебя есть в этом приложении)"""
    host: str = "127.0.0.1"
    port: int = 8000
    enable_api: bool = True


@dataclass
class NooForgeConfig:
    """Подключение к NooForge-Refiner"""
    base_url: str = "http://127.0.0.1:8877"
    api_key: Optional[str] = None  # если нужен
    ingest_text_path: str = "/api/ingest/text"
    ingest_file_path: str = "/api/ingest/file"
    rag_query_path: str = "/api/rag/query"
    default_collection: str = "chunks"


@dataclass
class AppConfig:
    """Общая конфигурация приложения"""
    transcriber: TranscriberConfig = field(default_factory=TranscriberConfig)
    chunker: ChunkerConfig = field(default_factory=ChunkerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: APIConfig = field(default_factory=APIConfig)
    nooforge: NooForgeConfig = field(default_factory=NooForgeConfig)

    config_file: str = "./data/config.json"  # Путь к файлу конфига

    def __post_init__(self):
        """Создаем необходимые директории"""
        os.makedirs(self.database.transcripts_dir, exist_ok=True)
        os.makedirs(self.database.chunks_dir, exist_ok=True)
        os.makedirs(Path(self.database.db_path).parent, exist_ok=True)

    def save_to_file(self):
        """Сохранить конфиг в JSON файл"""
        import json
        from dataclasses import asdict

        config_dict = {
            'transcriber': asdict(self.transcriber),
            'chunker': asdict(self.chunker),
            'database': asdict(self.database),
            'api': asdict(self.api),
            'nooforge': asdict(self.nooforge),
        }

        os.makedirs(Path(self.config_file).parent, exist_ok=True)

        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

    def load_from_file(self):
        """Загрузить конфиг из JSON файла"""
        import json

        if not os.path.exists(self.config_file):
            return False

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)

            if 'transcriber' in config_dict:
                for k, v in config_dict['transcriber'].items():
                    if hasattr(self.transcriber, k):
                        setattr(self.transcriber, k, v)

            if 'chunker' in config_dict:
                for k, v in config_dict['chunker'].items():
                    if hasattr(self.chunker, k):
                        setattr(self.chunker, k, v)

            if 'database' in config_dict:
                for k, v in config_dict['database'].items():
                    if hasattr(self.database, k):
                        setattr(self.database, k, v)

            if 'api' in config_dict:
                for k, v in config_dict['api'].items():
                    if hasattr(self.api, k):
                        setattr(self.api, k, v)

            if 'nooforge' in config_dict:
                for k, v in config_dict['nooforge'].items():
                    if hasattr(self.nooforge, k):
                        setattr(self.nooforge, k, v)

            return True
        except Exception as e:
            print(f"⚠️ Ошибка загрузки конфига: {e}")
            return False


# Глобальный конфиг (синглтон)
_config = None


def get_config() -> AppConfig:
    """Получить глобальный конфиг"""
    global _config
    if _config is None:
        _config = AppConfig()
        if _config.load_from_file():
            print(f"✅ Конфиг загружен из {_config.config_file}")
        else:
            print(f"ℹ️ Используется конфиг по умолчанию")
    return _config


def update_config(**kwargs):
    """Обновить конфиг и сохранить в файл"""
    global _config
    config = get_config()

    for key, value in kwargs.items():
        if '.' in key:
            # Вложенные атрибуты: transcriber.model_name
            parts = key.split('.')
            obj = config
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], value)
        else:
            setattr(config, key, value)

    config.save_to_file()
    return config


if __name__ == "__main__":
    cfg = get_config()
    print("Transcriber:", cfg.transcriber)
    print("Chunker:", cfg.chunker)
    print("Database:", cfg.database)
    print("API:", cfg.api)
    print("NooForge:", cfg.nooforge)

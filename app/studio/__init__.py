# app/studio/__init__.py
"""
Публичный фасад WhisperRAGStudio — сохраняет прежний API.
Внутри использует композицию модулей: common, transcribe, search, files, refiner, settings.
"""
from __future__ import annotations
import logging
from .common import StudioContext
from .transcribe import TranscribeModule
from .search import SearchModule
from .files import FilesModule
from .refiner import RefinerModule
from .settings import SettingsModule


log = logging.getLogger("whisper_rag_studio")


class WhisperRAGStudio:
    def __init__(self):
        self.ctx = StudioContext()
        # подмодули
        self.transcribe = TranscribeModule(self.ctx)
        self.search = SearchModule(self.ctx)
        self.files = FilesModule(self.ctx)
        self.refiner = RefinerModule(self.ctx)
        self.settings = SettingsModule(self.ctx)

    # ------------------------------------------------------------------
    # Совместимость со старым кодом: доступ к .config и .db как атрибутам
    # ------------------------------------------------------------------
    @property
    def config(self):
        """Совместимый доступ: studio.config → self.ctx.config"""
        return self.ctx.config

    @property
    def db(self):
        """Если где-то обращаются к studio.db — пробрасываем контекстную БД."""
        return self.ctx.db

    # ---------- Проксируем публичные методы (совместимо со старым кодом) ----------

    # validate/model
    def validate_model_path(self, model_path, use_faster_whisper):
        return self.settings.validate_model_path(model_path, use_faster_whisper)

    # transcribe / text
    def process_file(self, file, progress=None):
        return self.transcribe.process_file(file, progress)

    def process_text(self, text, progress=None):
        return self.transcribe.process_text(text, progress)

    # search
    def search_documents(self, query: str) -> str:
        return self.search.search_documents(query)

    # files / stats / lists
    def _stats_md(self) -> str:
        return self.files.stats_md()

    def get_files_for_display(self):
        return self.files.get_files_for_display()

    def refresh_files_display(self):
        return self.files.refresh_files_display()

    def refresh_files_dropdown(self):
        return self.files.refresh_files_dropdown()

    def refresh_files_lists_both(self):
        return self.files.refresh_files_lists_both()

    def refresh_ingest_dropdown(self):
        return self.files.refresh_ingest_dropdown()

    def render_files_list_html(self) -> str:
        return self.files.render_files_list_html()

    def view_transcript_by_id(self, file_id: int) -> str:
        return self.files.view_transcript_by_id(file_id)

    def delete_files_by_ids(self, file_ids):
        return self.files.delete_files_by_ids(file_ids)

    def delete_files_by_ids_from_json(self, ids_json: str):
        return self.files.delete_files_by_ids_from_json(ids_json)

    # settings
    def update_settings(self, *args, **kwargs):
        return self.settings.update_settings(*args, **kwargs)

    def update_refiner_settings(self, *args, **kwargs):
        return self.settings.update_refiner_settings(*args, **kwargs)

    def save_all_settings(self, *args, **kwargs):
        return self.settings.save_all_settings(*args, **kwargs)

    # refiner (ingest + rag)
    def ingest_transcript_by_id(self, file_id, source_id, collection):
        return self.refiner.ingest_transcript_by_id(file_id, source_id, collection)

    def ingest_file_direct(self, file, source_id, collection):
        return self.refiner.ingest_file_direct(file, source_id, collection)

    def rag_query(self, question, top_k, rerank_k, collection, filters_json):
        return self.refiner.rag_query(question, top_k, rerank_k, collection, filters_json)

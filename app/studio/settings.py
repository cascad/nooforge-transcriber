# app/studio/settings.py
from __future__ import annotations
from pathlib import Path
from typing import Tuple
from .common import StudioContext
from app.config import get_config, update_config


class SettingsModule:
    def __init__(self, ctx: StudioContext):
        self.ctx = ctx

    def validate_model_path(self, model_path: str | None, use_faster_whisper: bool) -> Tuple[bool, str]:
        if not model_path or not model_path.strip():
            return True, "✅ Будет использована автозагрузка модели"

        path = Path(model_path.strip()).resolve()
        if not path.exists():
            return False, f"❌ Путь не существует: {path}"
        if not path.is_dir():
            return False, f"❌ Это не директория: {path}"

        if use_faster_whisper:
            has_cfg = (path / "config.json").exists()
            has_model = any((path / f).exists()
                            for f in ("model.bin", "model.safetensors"))
            if not has_cfg:
                return False, f"❌ Не найден config.json в {path}"
            if not has_model:
                return False, f"❌ Не найдены model.bin/model.safetensors в {path}"
            total_mb = sum(f.stat().st_size for f in path.glob(
                "*") if f.is_file()) / 1024 / 1024
            which = "model.bin" if (
                path / "model.bin").exists() else "model.safetensors"
            return True, f"✅ Модель найдена: {path}\n💾 {total_mb:.1f} MB\n📁 Файлы: config.json, {which}"
        else:
            pts = list(path.glob("*.pt"))
            if not pts:
                return False, f"❌ Не найдены .pt файлы в {path}"
            total_mb = sum(f.stat().st_size for f in pts) / 1024 / 1024
            return True, f"✅ Модель найдена: {path}\n💾 {total_mb:.1f} MB\n📁 {', '.join(p.name for p in pts)}"

    # ---- update sections ----
    def update_settings(self, use_faster, model_name, model_path, device, use_vad, chunk_size, chunk_overlap) -> str:
        if model_path and model_path.strip():
            ok, vmsg = self.validate_model_path(model_path, use_faster)
            if not ok:
                return vmsg
            model_path_value = str(Path(model_path.strip()).resolve())
        else:
            model_path_value = None
            vmsg = "ℹ️ Модель будет загружена автоматически при первом использовании"

        update_config(**{
            "transcriber.use_faster_whisper": use_faster,
            "transcriber.model_name": model_name,
            "transcriber.model_path": model_path_value,
            "transcriber.device": device,
            "transcriber.use_vad": use_vad,
            "chunker.chunk_size": chunk_size,
            "chunker.chunk_overlap": chunk_overlap,
        })

        # Сбросить инстансы и перечитать конфиг корректно
        self.ctx.transcriber_loaded = False
        self.ctx.transcriber = None
        self.ctx.chunker = self.ctx.chunker.__class__()  # перезагрузка chunker
        # <-- просто перечитываем конфиг без тернарных фокусов
        self.ctx.config = get_config()

        msg = (
            "✅ **Настройки сохранены**\n\n"
            "💾 ./data/config.json\n"
            "🔄 Модель перезагрузится при следующем использовании\n\n"
            f"- Движок: {'Faster-Whisper' if use_faster else 'Whisper'}\n"
            f"- Модель: {model_name}\n"
            f"- Устройство: {device.upper()}\n"
            f"- VAD: {'✓' if use_vad else '✗'}\n"
            f"- Чанк: {chunk_size} символов\n"
            f"- Перекрытие: {chunk_overlap} символов\n\n"
            f"{vmsg}"
        )
        return msg

    def update_refiner_settings(self, base_url, api_key, ingest_text_path, ingest_file_path, rag_query_path, default_collection):
        update_config(**{
            "nooforge.base_url": (base_url or "").strip(),
            "nooforge.api_key": (api_key or "").strip() or None,
            "nooforge.ingest_text_path": (ingest_text_path or "/api/ingest/text").strip(),
            "nooforge.ingest_file_path": (ingest_file_path or "/api/ingest/file").strip(),
            "nooforge.rag_query_path": (rag_query_path or "/api/rag/query").strip(),
            "nooforge.default_collection": (default_collection or "chunks").strip(),
        })
        # Перечитать конфиг после записи
        self.ctx.config = get_config()
        return "✅ Настройки NooForge-Refiner сохранены"

    def save_all_settings(self, *args):
        (
            use_faster, model_name, model_path, device, use_vad, chunk_size, chunk_overlap,
            base_url, api_key, ingest_text_path, ingest_file_path, rag_query_path, default_collection
        ) = args
        local_msg = self.update_settings(
            use_faster, model_name, model_path, device, use_vad, chunk_size, chunk_overlap)
        ref_msg = self.update_refiner_settings(
            base_url, api_key, ingest_text_path, ingest_file_path, rag_query_path, default_collection)
        return f"{local_msg}\n\n{ref_msg}"

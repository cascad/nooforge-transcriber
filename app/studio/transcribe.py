# app/studio/transcribe.py
from __future__ import annotations
import logging
import os
from pathlib import Path
from datetime import datetime
import gradio as gr
from .common import StudioContext

log = logging.getLogger("whisper_rag_studio")


class TranscribeModule:
    def __init__(self, ctx: StudioContext):
        self.ctx = ctx

    def process_file(self, file, progress=gr.Progress()):
        if file is None:
            return "❌ Файл не выбран", "", self.ctx.stats_md()

        try:
            progress(0, desc="Подготовка…")
            self.ctx.ensure_transcriber()

            file_path = Path(file.name)
            file_size = os.path.getsize(file_path)

            # upsert file row
            import sqlite3
            try:
                cur = self.ctx.db.conn.execute(
                    "SELECT id, status FROM files WHERE filepath = ?", (str(file_path),))
                row = cur.fetchone()
                if row:
                    file_id, status = row
                    if status == "completed":
                        tr = self.ctx.db.get_transcript_by_file_id(file_id)
                        if tr and Path(tr["transcript_path"]).exists():
                            full = Path(tr["transcript_path"]).read_text(
                                encoding="utf-8")
                            msg = (
                                "⚠️ **Файл уже обработан ранее**\n\n"
                                f"📄 {file_path.name}\n"
                                f"- Слов: {tr['word_count']}\n- Длительность: {tr['duration_seconds']:.1f} сек\n"
                                f"- Язык: {tr['language']}\n"
                                "💡 Показан существующий транскрипт."
                            )
                            return msg, full, self.ctx.stats_md()
                    self.ctx.db.update_file_status(file_id, "processing")
                else:
                    file_id = self.ctx.db.add_file(
                        filename=file_path.name,
                        filepath=str(file_path),
                        file_type=file_path.suffix,
                        file_size=file_size,
                    )
                    self.ctx.db.update_file_status(file_id, "processing")
            except sqlite3.IntegrityError:
                return "❌ Этот файл уже обрабатывается или был обработан. Обновите страницу.", "", self.ctx.stats_md()

            # transcribe
            def cb(v, d): progress(v, desc=d)
            full_text, meta = self.ctx.transcriber.transcribe_file(
                str(file_path), progress_callback=cb)

            # save transcript
            tr_path = Path(self.ctx.config.database.transcripts_dir) / \
                f"{file_id}_{file_path.stem}.txt"
            tr_path.write_text(full_text, encoding="utf-8")

            tr_id = self.ctx.db.add_transcript(
                file_id=file_id,
                transcript_path=str(tr_path),
                text_preview=full_text[:500],
                word_count=len(full_text.split()),
                duration_seconds=meta.get("duration", 0),
                language=meta.get("language", "ru"),
                model_used=meta.get("model", "unknown"),
            )

            progress(0.9, desc="Нарезка на чанки…")
            chunks = self.ctx.chunker.chunk_text(full_text)
            self.ctx.db.add_chunks(tr_id, chunks)

            self.ctx.db.update_file_status(file_id, "completed")

            msg = (
                "✅ **Файл обработан**\n\n"
                f"📄 {file_path.name}\n"
                f"- Длительность: {meta.get('duration', 0):.1f} сек\n"
                f"- Слов: {len(full_text.split())}\n"
                f"- Сегментов: {meta.get('total_segments', 0)}\n"
                f"- Отфильтровано: {meta.get('filtered_segments', 0)}\n"
                f"- Чанков: {len(chunks)}\n"
                f"🎯 Модель: {meta.get('model', 'unknown')}, 🌍 {meta.get('language', 'ru')}"
            )
            return msg, full_text, self.ctx.stats_md()
        except Exception as e:
            log.exception("process_file failed")
            return f"❌ Ошибка обработки: {e}", "", self.ctx.stats_md()

    def process_text(self, text, progress=gr.Progress()):
        if not text or not text.strip():
            return "❌ Текст пустой", self.ctx.stats_md()
        try:
            progress(0.5, desc="Обработка текста…")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"text_{ts}.txt"
            fpath = Path(self.ctx.config.database.transcripts_dir) / fname
            fpath.write_text(text, encoding="utf-8")

            file_id = self.ctx.db.add_file(
                filename=fname, filepath=str(fpath), file_type=".txt", file_size=len(text.encode("utf-8"))
            )
            tr_id = self.ctx.db.add_transcript(
                file_id=file_id,
                transcript_path=str(fpath),
                text_preview=text[:500],
                word_count=len(text.split()),
                duration_seconds=0,
                language="ru",
                model_used="manual_input",
            )
            progress(0.8, desc="Нарезка на чанки…")
            chunks = self.ctx.chunker.chunk_text(text)
            self.ctx.db.add_chunks(tr_id, chunks)
            self.ctx.db.update_file_status(file_id, "completed")

            msg = (
                "✅ **Текст обработан**\n\n"
                f"- Слов: {len(text.split())}\n- Символов: {len(text)}\n- Чанков: {len(chunks)}"
            )
            return msg, self.ctx.stats_md()
        except Exception as e:
            log.exception("process_text failed")
            return f"❌ Ошибка: {e}", self.ctx.stats_md()

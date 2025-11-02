# app/studio/files.py
from __future__ import annotations
import json
from pathlib import Path
from typing import List
from .common import StudioContext


class FilesModule:
    def __init__(self, ctx: StudioContext):
        self.ctx = ctx

    # stats
    def stats_md(self) -> str:
        return self.ctx.stats_md()

    # lists
    def get_files_for_display(self):
        return self.ctx.files_for_display()

    def refresh_files_display(self):
        """Для старого интерфейса (CheckboxGroup + viewer)"""
        choices = self.ctx.files_for_display()
        return (
            dict(choices=choices, value=[]),  # CheckboxGroup
            ""                                # очистить viewer
        )

    def refresh_files_dropdown(self):
        return dict(choices=self.ctx.files_for_display(), value=None)

    def refresh_files_lists_both(self):
        choices = self.ctx.files_for_display()
        return (
            dict(choices=choices, value=None),  # dropdown viewer
            dict(choices=choices, value=[]),    # checkbox delete
            ""                                  # clear viewer
        )

    def refresh_ingest_dropdown(self):
        return dict(choices=self.ctx.files_for_display(), value=None)

    def render_files_list_html(self) -> str:
        return self.ctx.render_files_list_html()

    # view / delete
    def view_transcript_by_id(self, file_id: int) -> str:
        if not file_id:
            return ""
        tr = self.ctx.db.get_transcript_by_file_id(file_id)
        if not tr:
            return "❌ Транскрипт не найден"
        p = Path(tr["transcript_path"])
        return p.read_text(encoding="utf-8") if p.exists() else "❌ Файл транскрипта отсутствует"

    def delete_files_by_ids(self, file_ids: List[int]):
        if not file_ids:
            return "⚠️ Выберите файлы для удаления", *self.refresh_files_display()
        deleted = []
        for fid in file_ids:
            fi = self.ctx.db.get_file_by_id(fid)
            if fi:
                deleted.append(fi["filename"])
                tr = self.ctx.db.get_transcript_by_file_id(fid)
                if tr:
                    Path(tr["transcript_path"]).unlink(missing_ok=True)
                self.ctx.db.delete_file(fid)
        msg = "✅ Удалено файлов: " + str(len(deleted))
        if deleted:
            msg += "\n\n" + "\n".join(f"• {n}" for n in deleted)
        return msg, *self.refresh_files_display()

    def delete_files_by_ids_from_json(self, ids_json: str):
        try:
            ids = json.loads(ids_json or "[]")
            if not isinstance(ids, list):
                return "❌ Неверный формат выбранных ID", self.render_files_list_html(), ""
            ids_int = [int(x) for x in ids if str(x).isdigit()]
            # реальное удаление
            deleted = []
            for fid in ids_int:
                fi = self.ctx.db.get_file_by_id(fid)
                if fi:
                    deleted.append(fi["filename"])
                    tr = self.ctx.db.get_transcript_by_file_id(fid)
                    if tr:
                        Path(tr["transcript_path"]).unlink(missing_ok=True)
                    self.ctx.db.delete_file(fid)
            msg = "✅ Удалено файлов: " + str(len(deleted))
            if deleted:
                msg += "\n\n" + "\n".join(f"• {n}" for n in deleted)
            return msg, self.render_files_list_html(), ""
        except Exception as e:
            return f"❌ Ошибка: {e}", self.render_files_list_html(), ""

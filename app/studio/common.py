# app/studio/common.py
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.config import get_config  # update_config может быть в других модулях
from app.database import Database
from app.chunker import TextChunker

from transcriber import Transcriber

log = logging.getLogger("whisper_rag_studio")


@dataclass
class StudioContext:
    """Общий контекст и утилиты для модулей."""
    config: any = field(default_factory=get_config)
    db: Database = field(default_factory=Database)
    transcriber: Optional[any] = None
    transcriber_loaded: bool = False
    chunker: TextChunker = field(default_factory=TextChunker)

    # ---- helpers ----
    def ensure_transcriber(self):
        if not self.transcriber_loaded:
            if Transcriber is None:
                raise RuntimeError("Transcriber class is not available")
            self.transcriber = Transcriber()
            self.transcriber_loaded = True

    def headers_refiner(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = (self.config.nooforge.api_key or "").strip(
        ) if self.config.nooforge.api_key else ""
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @staticmethod
    def join_url(base: str | None, path: str) -> str:
        if not base:
            return path
        base = base[:-1] if base.endswith("/") else base
        path = path if path.startswith("/") else ("/" + path)
        return base + path

    # ---- stats ----
    def stats_md(self) -> str:
        s = self.db.get_stats()
        return (
            "📊 **Статистика БД:**\n"
            f"- Всего файлов: {s['total_files']}\n"
            f"- Обработано: {s['processed_files']}\n"
            f"- Транскриптов: {s['total_transcripts']}\n"
            f"- Чанков: {s['total_chunks']}\n"
            f"- Размер: {s['total_size_mb']} МБ"
        )

    # ---- files (DESC) ----
    def files_for_display(self, limit: int = 500) -> List[tuple[str, int]]:
        files = self.db.get_all_files() or []
        files = sorted(files, key=lambda x: x["created_at"], reverse=True)
        out: List[tuple[str, int]] = []
        for f in files[:limit]:
            status = {"completed": "✅", "processing": "⏳",
                      "failed": "❌", "pending": "⏸️"}.get(f["status"], "❓")
            info = str(f["created_at"])[:19]
            if f["status"] == "completed":
                tr = self.db.get_transcript_by_file_id(f["id"])
                if tr:
                    info += f" • {tr['word_count']} слов"
            label = f"{status} {f['filename']} • {info}"
            out.append((label, f["id"]))
        return out

    def delete_files_by_ids_list(self, ids: list[int]):
        """Вернуть Markdown-отчёт об удалении, совместимый с текущим UI."""
        if not ids:
            return "ℹ️ Нечего удалять."
        try:
            # у тебя, вероятно, уже есть метод удаления по JSON;
            # дернем на прямую БД/хранилище, как реализовано у тебя:
            ok, fail = 0, 0
            for fid in ids:
                try:
                    self.db.delete_file_and_transcript(fid)
                    ok += 1
                except Exception:
                    fail += 1
            msg = f"✅ Удалено: **{ok}**, Ошибок: **{fail}**"
            return msg
        except Exception as e:
            return f"❌ Ошибка удаления: {e}"

    def render_files_list_html(self, marked: list[int] | None = None) -> str:
        marked = set(marked or [])
        items = self.files_for_display()

        rows = []
        for label, fid in items:
            mark_class = "marked" if fid in marked else ""
            rows.append(
                f'<div class="file-row {mark_class}" data-id="{fid}">'
                f'  <span class="cb" data-id="{fid}"></span>'
                f'  <span class="label" data-id="{fid}">{label}</span>'
                f'</div>'
            )
        if not rows:
            rows.append('<div class="empty">Нет файлов</div>')

        html = "<div class='file-list'>\n" + "\n".join(rows) + "\n</div>"

        script = r"""
    <script>
    (function(){
    const root = document.querySelector('#files_list .file-list');
    if(!root) return;

    const selectedInput = document.querySelector('#files_selected input, #files_selected textarea');
    const viewInput     = document.querySelector('#files_view_id input, #files_view_id textarea');

    function getMarked() { try { return JSON.parse(selectedInput.value||"[]"); } catch{ return []; } }
    function setMarked(arr){
        selectedInput.value = JSON.stringify(arr);
        selectedInput.dispatchEvent(new Event('input',{bubbles:true}));
        selectedInput.dispatchEvent(new Event('change',{bubbles:true}));
    }
    function sync(){
        const s = new Set(getMarked());
        root.querySelectorAll('.file-row').forEach(r=>{
        const fid = parseInt(r.dataset.id,10);
        if(s.has(fid)) r.classList.add('marked'); else r.classList.remove('marked');
        });
    }

    root.onclick = (e)=>{
        const row = e.target.closest('.file-row'); if(!row) return;
        const fid = parseInt(row.dataset.id,10); if(!fid) return;

        // клик по чекбоксу → toggle mark
        if(e.target.classList.contains('cb')){
        e.stopPropagation();
        let arr = getMarked();
        if(arr.includes(fid)) arr = arr.filter(x=>x!==fid); else arr.push(fid);
        setMarked(arr); sync(); return;
        }

        // иначе → показать транскрипт
        viewInput.value = String(fid);
        viewInput.dispatchEvent(new Event('input', {bubbles:true}));
        viewInput.dispatchEvent(new Event('change',{bubbles:true}));
    };

    sync();
    })();
    </script>
    """
        return html + script

# app/studio/search.py
from __future__ import annotations
from .common import StudioContext


class SearchModule:
    def __init__(self, ctx: StudioContext):
        self.ctx = ctx

    def search_documents(self, query: str) -> str:
        if not query or not query.strip():
            return "⚠️ Введите поисковый запрос"
        try:
            res = self.ctx.db.search_transcripts(query, limit=10) or []
            if not res:
                return "🔍 Ничего не найдено"
            out = [f"🔍 **Найдено**: {len(res)}", ""]
            for i, r in enumerate(res, 1):
                date = str(r["created_at"])[:19]
                preview = (r["text_preview"] or "")[:200]
                out.append(
                    f"**{i}. {r['filename']}**\n📅 {date}\n📄 {preview}…\n\n---")
            return "\n\n".join(out)
        except Exception as e:
            return f"❌ Ошибка поиска: {e}"

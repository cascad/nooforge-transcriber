# app/studio/refiner.py
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Tuple, List, Dict, Any
import requests
from .common import StudioContext

log = logging.getLogger("whisper_rag_studio")


class RefinerModule:
    def __init__(self, ctx: StudioContext):
        self.ctx = ctx

    # -------- Ingest --------
    def ingest_transcript_by_id(self, file_id, source_id, collection):
        if not file_id:
            return "⚠️ Выберите файл", ""
        tr = self.ctx.db.get_transcript_by_file_id(file_id)
        if not tr:
            return "❌ Транскрипт не найден", ""
        p = Path(tr["transcript_path"])
        if not p.exists():
            return "❌ Файл транскрипта отсутствует", ""
        text = p.read_text(encoding="utf-8")
        payload = {
            "text": text,
            "source_id": source_id or f"file://{file_id}",
            "collection": collection or (self.ctx.config.nooforge.default_collection or "chunks"),
        }
        url = self.ctx.join_url(
            self.ctx.config.nooforge.base_url, self.ctx.config.nooforge.ingest_text_path)
        log.info("INGEST TEXT → %s | bytes=%d | source_id=%s | collection=%s",
                 url, len(text.encode('utf-8')), payload["source_id"], payload["collection"])
        try:
            r = requests.post(url, data=json.dumps(payload),
                              headers=self.ctx.headers_refiner(), timeout=120)
            if 200 <= r.status_code < 300:
                try:
                    data = r.json()
                except Exception:
                    data = {"ok": True, "raw": r.text}
                return "✅ Отправлено в Refiner", "```json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```"
            log.error("INGEST TEXT ERROR POST → %s | status=%d | body=%s",
                      url, r.status_code, r.text)
            return f"❌ Refiner вернул {r.status_code}", f"Тело ответа:\n\n{r.text}"
        except Exception as e:
            log.exception("INGEST TEXT exception")
            return f"❌ Ошибка отправки: {e}", ""

    def ingest_file_direct(self, file, source_id, collection):
        if file is None:
            return "⚠️ Файл не выбран", ""
        url = self.ctx.join_url(
            self.ctx.config.nooforge.base_url, self.ctx.config.nooforge.ingest_file_path)
        headers = dict(self.ctx.headers_refiner())
        headers.pop("Content-Type", None)
        filename = Path(file.name).name
        files = {"file": (filename, open(file.name, "rb"))}
        data = {
            "source_id": source_id or f"upload://{filename}",
            "collection": collection or (self.ctx.config.nooforge.default_collection or "chunks"),
        }
        log.info("INGEST FILE → %s | file=%s | source_id=%s | collection=%s",
                 url, filename, data["source_id"], data["collection"])
        try:
            resp = requests.post(url, headers=headers,
                                 files=files, data=data, timeout=300)
        finally:
            try:
                files["file"][1].close()
            except Exception:
                pass
        if resp.status_code // 100 == 2:
            try:
                data_out = resp.json()
            except Exception:
                data_out = {"ok": True, "raw": resp.text}
            return "✅ Файл отправлен в Refiner", "```json\n" + json.dumps(data_out, ensure_ascii=False, indent=2) + "\n```"
        log.error("INGEST FILE ERROR POST → %s | status=%d | body=%s",
                  url, resp.status_code, resp.text)
        return f"❌ Refiner вернул {resp.status_code}", f"Тело ответа:\n\n{resp.text}"

    # -------- RAG --------
    def rag_query(self, question, top_k, rerank_k, collection, filters_json):
        if not question or not question.strip():
            return "⚠️ Введите запрос", ""
        common = {
            "top_k": int(top_k or 8),
            "rerank_k": int(rerank_k or 0),
            "collection": collection or (self.ctx.config.nooforge.default_collection or "chunks"),
        }
        if filters_json and str(filters_json).strip():
            try:
                common["filters"] = json.loads(str(filters_json))
            except Exception as e:
                return f"❌ Неверный JSON в фильтрах: {e}", ""
        url = self.ctx.join_url(
            self.ctx.config.nooforge.base_url, self.ctx.config.nooforge.rag_query_path)
        headers = self.ctx.headers_refiner()

        # 1) q
        payload_q = dict(common)
        payload_q["q"] = question.strip()
        log.info("RAG QUERY (try=q) → %s | payload=%s", url,
                 json.dumps(payload_q, ensure_ascii=False))
        r = requests.post(url, data=json.dumps(payload_q),
                          headers=headers, timeout=120)
        if r.status_code // 100 != 2:
            body = r.text
            log.error("RAG QUERY ERROR (try=q) POST → %s | status=%d | body=%s",
                      url, r.status_code, body)
            retry = (r.status_code == 422 and
                     ("missing field `query`" in body or "field `query`" in body or
                      "missing field `q`" in body or "field `q`" in body))
            if retry:
                payload_query = dict(common)
                payload_query["query"] = question.strip()
                log.info("RAG QUERY RETRY (try=query) → %s | payload=%s",
                         url, json.dumps(payload_query, ensure_ascii=False))
                r2 = requests.post(url, data=json.dumps(
                    payload_query), headers=headers, timeout=120)
                if r2.status_code // 100 != 2:
                    log.error(
                        "RAG QUERY ERROR (try=query) POST → %s | status=%d | body=%s", url, r2.status_code, r2.text)
                    return f"❌ Refiner вернул {r2.status_code}", f"Тело ответа:\n\n{r2.text}"
                try:
                    data = r2.json()
                except Exception:
                    data = {"raw": r2.text}
                return self._render_rag_answer(data)
            return f"❌ Refiner вернул {r.status_code}", f"Тело ответа:\n\n{body}"

        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        return self._render_rag_answer(data)

    @staticmethod
    def _render_rag_answer(data: Dict[str, Any]) -> tuple[str, str]:
        parts: List[str] = []
        if "answer" in data:
            parts.append(f"### 🧠 Ответ\n\n{data['answer']}\n")
        results = data.get("results")
        if isinstance(results, list) and results:
            parts.append("### 📚 Источники\n")
            for i, r in enumerate(results, 1):
                score = r.get("score")
                src = r.get("source_id") or r.get("source") or "-"
                snippet = r.get("snippet") or r.get("text") or ""
                score_str = f" (score: {score:.3f})" if isinstance(
                    score, (int, float)) else ""
                parts.append(
                    f"**{i}.** `{src}`{score_str}\n\n> {snippet[:500]}{('…' if len(snippet) > 500 else '')}\n\n---\n")
        if not parts:
            parts.append("ℹ️ Пустой ответ от Refiner")
        return "✅ Запрос выполнен", "\n".join(parts)

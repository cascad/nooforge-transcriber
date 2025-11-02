# app/ui/tabs.py
from __future__ import annotations
import gradio as gr
from app.ui.js import RESTORE_ACTIVE_TAB_JS, SAVE_ACTIVE_TAB_JS
from app.studio import WhisperRAGStudio
from app.studio.settings import SettingsModule

# CSS: вертикальные списки в «Файлы» и вертикальный radio в «Ingest»
CUSTOM_CSS = """
.files-two-cols { gap: 16px; }

/* Левая колонка (просмотр) — вертикальный список */
#files_radio_list .wrap {
  display: grid !important;
  grid-template-columns: 1fr !important;
  gap: 6px !important;
}
#files_radio_list .wrap > label {
  width: 100% !important;
  margin: 0 !important;
  padding: 8px 10px !important;
  border-radius: 8px !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
  background: var(--block-background-fill) !important;
}
#files_radio_list .wrap > label:hover { background: rgba(255,255,255,0.06) !important; }

/* Правая колонка (удаление) — вертикальный список */
#files_checks_list .wrap {
  display: grid !important;
  grid-template-columns: 1fr !important;
  gap: 6px !important;
}
#files_checks_list .wrap > label {
  width: 100% !重要;
  margin: 0 !important;
  padding: 8px 10px !important;
  border-radius: 8px !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
  background: var(--block-background-fill) !important;
}
#files_checks_list .wrap > label:hover { background: rgba(255,255,255,0.06) !important; }

/* Одинаковая высота и скролл колонок в «Файлы» */
#files_radio_list, #files_checks_list {
  max-height: 420px;
  overflow-y: auto;
  padding-right: 4px;
}

/* Ingest: вертикальный radio-список */
#ingest_radio_list .wrap {
  display: grid !important;
  grid-template-columns: 1fr !important;
  gap: 6px !important;
}
#ingest_radio_list .wrap > label {
  width: 100% !important;
  margin: 0 !important;
  padding: 8px 10px !important;
  border-radius: 8px !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
  background: var(--block-background-fill) !important;
}
#ingest_radio_list .wrap > label:hover { background: rgba(255,255,255,0.06) !important; }
"""

# Глобальный хоткей: Enter → отправка RAG, Shift+Enter → перенос строки.
# Вешаем capture-listener один раз на документ (и пере-вешиваем при входе на вкладку).
RAG_HOTKEY_JS = """
() => {
  const root = document.getElementById('rag_question');
  if (!root) return;

  const KEY = '__ragDocKeyHook';
  if (window[KEY]) {
    document.removeEventListener('keydown', window[KEY], true);
    window[KEY] = null;
  }

  window[KEY] = function(ev) {
    if (ev.key !== 'Enter') return;
    const ta = root.querySelector('[data-testid="textbox"] textarea');
    if (!ta) return;
    if (document.activeElement !== ta) return;

    if (ev.shiftKey) {
      ev.stopImmediatePropagation();
      return;
    }

    ev.preventDefault();
    ev.stopImmediatePropagation();
    const btn = document.getElementById('rag_ask_btn');
    if (btn) btn.click();
  };

  document.addEventListener('keydown', window[KEY], true);
}
"""


def _encode(label: str, fid: int) -> str:
    return f"{fid} ::: {label}"


def _decode(s: str) -> int:
    return int(s.split(" ::: ", 1)[0])


def build_interface(studio: WhisperRAGStudio) -> gr.Blocks:
    with gr.Blocks(title="Whisper RAG Studio", theme=gr.themes.Soft(), css=CUSTOM_CSS) as demo:
        _init = gr.State("")
        _hotkey = gr.State("")

        # восстановление активной вкладки
        demo.load(fn=lambda: "", inputs=None, outputs=[
                  _init], js=RESTORE_ACTIVE_TAB_JS)
        # глобально повесим хоткей при загрузке приложения
        demo.load(fn=lambda: "", inputs=None,
                  outputs=[_hotkey], js=RAG_HOTKEY_JS)

        gr.Markdown("# 🎤 Whisper RAG Studio")

        with gr.Tabs():
            # ------------------------ ТРАНСКРИБАЦИЯ ------------------------
            with gr.Tab("📝 Транскрибация") as tab_tr:
                tab_tr.select(fn=lambda: "", inputs=None, outputs=[
                              _init], js=SAVE_ACTIVE_TAB_JS("📝 Транскрибация"))

                with gr.Row():
                    with gr.Column(scale=2):
                        file_input = gr.File(
                            label="Аудио/Видео файл",
                            file_count="single",
                            file_types=[
                                ".mp3", ".wav", ".m4a", ".flac", ".ogg",
                                ".mp4", ".mkv", ".avi", ".mov", ".webm"
                            ]
                        )
                        text_input = gr.Textbox(
                            label="Или введите текст вручную",
                            placeholder="Вставьте текст…",
                            lines=10
                        )
                        with gr.Row():
                            btn_proc_file = gr.Button(
                                "🎵 Обработать файл", variant="primary")
                            btn_proc_text = gr.Button("📄 Обработать текст")
                    with gr.Column(scale=1):
                        stats_md = gr.Markdown(studio._stats_md())

                result_md = gr.Markdown()
                transcript_tb = gr.Textbox(
                    label="Транскрипт", lines=15, max_lines=20, show_copy_button=True)

                # Пробрасываем progress, чтобы внутри не был None
                def _process_file_guard(f, progress=gr.Progress(track_tqdm=True)):
                    if f is None:
                        return ("ℹ️ Файл не выбран.", "", studio._stats_md())
                    return studio.process_file(f, progress=progress)

                def _process_text_guard(txt, progress=gr.Progress(track_tqdm=True)):
                    return studio.process_text(txt, progress=progress)

                btn_proc_file.click(_process_file_guard, [file_input], [
                                    result_md, transcript_tb, stats_md])
                btn_proc_text.click(_process_text_guard, [
                                    text_input], [result_md, stats_md])

            # ------------------------ ПОИСК ------------------------
            with gr.Tab("🔍 Поиск") as tab_search:
                tab_search.select(fn=lambda: "", inputs=None, outputs=[
                                  _init], js=SAVE_ACTIVE_TAB_JS("🔍 Поиск"))

                q = gr.Textbox(label="Запрос", lines=2,
                               placeholder="Введите запрос и нажмите Enter")
                btn_search = gr.Button("🔍 Искать", variant="primary")
                out_search = gr.Markdown()

                btn_search.click(studio.search_documents, [q], [out_search])
                q.submit(studio.search_documents, [q], [out_search])

            # ------------------------ ФАЙЛЫ (две вертикальные колонки) ------------------------
            with gr.Tab("📁 Файлы") as tab_files:
                tab_files.select(fn=lambda: "", inputs=None, outputs=[
                                 _init], js=SAVE_ACTIVE_TAB_JS("📁 Файлы"))

                gr.Markdown("Слева — просмотр, справа — пометки для удаления")

                def _choices():
                    return [_encode(label, fid) for label, fid in studio.get_files_for_display()]

                with gr.Row(elem_classes=["files-two-cols"]):
                    files_radio = gr.Radio(
                        label="Просмотр",
                        choices=_choices(),
                        value=None,
                        elem_id="files_radio_list",
                    )
                    files_checks = gr.CheckboxGroup(
                        label="Удаление",
                        choices=_choices(),
                        value=[],
                        elem_id="files_checks_list",
                    )

                with gr.Row():
                    btn_refresh = gr.Button("🔄 Обновить списки")
                    btn_delete = gr.Button(
                        "🗑️ Удалить выбранные", variant="stop")

                tr_view = gr.Textbox(label="Транскрипт",
                                     lines=28, show_copy_button=True)
                action_md = gr.Markdown()

                def _show(sel):
                    if not sel:
                        return ""
                    return studio.view_transcript_by_id(_decode(sel))

                files_radio.change(_show, [files_radio], [tr_view])

                def _refresh():
                    ch = _choices()
                    return (
                        gr.update(choices=ch, value=None),
                        gr.update(choices=ch, value=[]),
                        ""
                    )

                # автообновление при входе во вкладку «Файлы»
                gr.on(triggers=[tab_files.select], fn=_refresh, inputs=None, outputs=[
                      files_radio, files_checks, tr_view])

                # ручной refresh
                btn_refresh.click(
                    _refresh, None, [files_radio, files_checks, tr_view])

                def _delete(selected_list):
                    if not selected_list:
                        # 4 выхода: action_md, files_radio, files_checks, tr_view
                        return "ℹ️ Нечего удалять.", *_refresh()

                    ids = [_decode(s) for s in selected_list]
                    raw_msg = studio.delete_files_by_ids(ids)

                    # Гарантированно превращаем в строку для Markdown:
                    if isinstance(raw_msg, str):
                        msg = raw_msg
                    elif raw_msg is None:
                        msg = "✅ Удаление выполнено."
                    elif isinstance(raw_msg, (list, tuple, set)):
                        msg = "\n".join(map(str, raw_msg))
                    else:
                        msg = str(raw_msg)

                    return msg, *_refresh()

                btn_delete.click(_delete, [files_checks], [
                                 action_md, files_radio, files_checks, tr_view])

            # ------------------------ INGEST (Radio вертикально, один файл) ------------------------
            with gr.Tab("📤 Ingest → NooForge") as tab_ingest:
                tab_ingest.select(fn=lambda: "", inputs=None, outputs=[
                                  _init], js=SAVE_ACTIVE_TAB_JS("📤 Ingest → NooForge"))

                def _choices_ing():
                    return [_encode(label, fid) for label, fid in studio.get_files_for_display()]

                ingest_radio = gr.Radio(
                    label="Выберите файл (один)",
                    choices=_choices_ing(),
                    value=None,
                    elem_id="ingest_radio_list",
                )
                with gr.Row():
                    src_id = gr.Textbox(label="Source ID",
                                        placeholder="file://notes или свой ID")
                    coll = gr.Textbox(
                        label="Коллекция", value=studio.config.nooforge.default_collection or "chunks")
                btn_ing = gr.Button("📤 Отправить", variant="primary")

                ingest_status = gr.Markdown()
                ingest_payload = gr.Markdown()

                # автообновление при входе во вкладку «Ingest»
                gr.on(
                    triggers=[tab_ingest.select],
                    fn=lambda: gr.update(choices=_choices_ing(), value=None),
                    inputs=None,
                    outputs=[ingest_radio],
                )

                def _ingest(sel, src, c):
                    if not sel:
                        return ("ℹ️ Не выбран файл.", "")
                    return studio.ingest_transcript_by_id(_decode(sel), src, c)

                btn_ing.click(_ingest, [ingest_radio, src_id, coll], [
                              ingest_status, ingest_payload])

            # ------------------------ RAG (Enter → отправка, Shift+Enter → перенос) ------------------------
            with gr.Tab("🧠 RAG") as tab_rag:
                tab_rag.select(fn=lambda: "", inputs=None, outputs=[
                               _init], js=SAVE_ACTIVE_TAB_JS("🧠 RAG"))

                with gr.Row():
                    question = gr.Textbox(
                        label="Вопрос",
                        lines=4,
                        placeholder="Enter — отправить, Shift+Enter — перенос",
                        elem_id="rag_question",  # важно для JS
                    )
                    with gr.Column(scale=1):
                        top_k = gr.Number(label="top_k", value=8, precision=0)
                        rerank_k = gr.Number(
                            label="rerank_k", value=0, precision=0)
                        coll_rag = gr.Textbox(
                            label="Коллекция", value=studio.config.nooforge.default_collection or "chunks")
                filters_json = gr.Textbox(
                    label="Фильтры (JSON, опционально)", lines=3, placeholder='{"source_id":"file://notes"}')

                btn_rag = gr.Button(
                    "🧠 Спросить", variant="primary", elem_id="rag_ask_btn")
                rag_status = gr.Markdown()
                rag_output = gr.Markdown()

                btn_rag.click(
                    studio.rag_query,
                    inputs=[question, top_k, rerank_k, coll_rag, filters_json],
                    outputs=[rag_status, rag_output],
                )

                # при входе во вкладку — повторно навешиваем хоткей
                gr.on(triggers=[tab_rag.select], fn=lambda: "",
                      inputs=None, outputs=[_hotkey], js=RAG_HOTKEY_JS)

            # ------------------------ ⚙️ SETTINGS (единая кнопка сохранения) ------------------------
            with gr.Tab("⚙️ Settings") as tab_settings:
                tab_settings.select(fn=lambda: "", inputs=None, outputs=[_init], js=SAVE_ACTIVE_TAB_JS("⚙️ Settings"))
                cfg = studio.config
                settings = SettingsModule(studio.ctx)

                gr.Markdown("### Локальные настройки (Whisper / Chunker)")

                with gr.Row():
                    use_faster = gr.Checkbox(
                        label="Использовать Faster-Whisper",
                        value=bool(cfg.transcriber.use_faster_whisper),
                    )
                    model_name = gr.Textbox(
                        label="Модель (алиас)",
                        value=cfg.transcriber.model_name or "large-v3",
                        placeholder="small / medium / large-v3 …",
                    )
                    device = gr.Dropdown(
                        label="Устройство",
                        choices=["cuda", "cpu"],
                        value=(cfg.transcriber.device or "cuda"),
                    )

                with gr.Row():
                    model_path = gr.Textbox(
                        label="Путь к модели (опционально)",
                        value=cfg.transcriber.model_path or "",
                        placeholder="Если пусто — автозагрузка модели",
                    )
                    use_vad = gr.Checkbox(
                        label="VAD-фильтр",
                        value=bool(cfg.transcriber.use_vad),
                    )

                with gr.Row():
                    chunk_size = gr.Number(
                        label="Chunk size (символов)",
                        value=int(cfg.chunker.chunk_size),
                        precision=0,
                    )
                    chunk_overlap = gr.Number(
                        label="Chunk overlap (символов)",
                        value=int(cfg.chunker.chunk_overlap),
                        precision=0,
                    )

                gr.Markdown("### NooForge-Refiner")

                with gr.Row():
                    base_url = gr.Textbox(
                        label="Base URL",
                        value=cfg.nooforge.base_url or "http://127.0.0.1:8090",
                        placeholder="http://host:port",
                    )
                    api_key = gr.Textbox(
                        label="API Key (если нужен)",
                        value=cfg.nooforge.api_key or "",
                        type="password",
                    )

                with gr.Row():
                    ingest_text_path = gr.Textbox(
                        label="Ingest Text path",
                        value=cfg.nooforge.ingest_text_path or "/api/ingest/text",
                    )
                    ingest_file_path = gr.Textbox(
                        label="Ingest File path",
                        value=cfg.nooforge.ingest_file_path or "/api/ingest/file",
                    )

                with gr.Row():
                    rag_query_path = gr.Textbox(
                        label="RAG Query path",
                        value=cfg.nooforge.rag_query_path or "/api/rag/query",
                    )
                    default_collection = gr.Textbox(
                        label="Коллекция по умолчанию",
                        value=cfg.nooforge.default_collection or "chunks",
                    )

                save_btn = gr.Button("💾 Сохранить все настройки", variant="primary")
                save_status = gr.Markdown()

                save_btn.click(
                    fn=settings.save_all_settings,
                    inputs=[
                        use_faster, model_name, model_path, device, use_vad,
                        chunk_size, chunk_overlap,
                        base_url, api_key, ingest_text_path, ingest_file_path, rag_query_path, default_collection
                    ],
                    outputs=[save_status],
                )

    return demo

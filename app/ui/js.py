# app/ui/js.py
"""
JS-строки для Gradio callbacks (сохранение/восстановление активной вкладки).
"""

RESTORE_ACTIVE_TAB_JS = r"""
() => {
  const label = localStorage.getItem('whisper_rag_active_tab') || '';
  if (!label) return '';
  const tabs = document.querySelectorAll('[role="tab"]');
  for (const t of tabs) {
    const txt = (t.innerText || t.textContent || '').trim();
    if (txt.startsWith(label)) { t.click(); break; }
  }
  return '';
}
"""


def SAVE_ACTIVE_TAB_JS(label: str) -> str:
    return f"""
() => {{
  localStorage.setItem('whisper_rag_active_tab','{label}');
  return '';
}}
""".strip()

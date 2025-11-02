# app/main.py
"""
Whisper RAG Studio — точка входа
Запуск Gradio UI + проверка CUDA + аккуратное завершение.
"""
import os
import signal
import sys
import gradio as gr

from app.config import get_config, update_config
from app.studio import WhisperRAGStudio
from app.ui.tabs import build_interface


def check_cuda_availability():
    """Лёгкая проверка CUDA/cuDNN. Возвращает 'cuda' или 'cpu'."""
    try:
        import torch
    except Exception:
        print("⚠️ torch не найден, работаем на CPU")
        return "cpu"

    print("\n" + "=" * 60)
    print("🔍 Проверка системы...")
    print("=" * 60)

    if not torch.cuda.is_available():
        print("ℹ️ CUDA не доступна → CPU")
        return "cpu"

    print("✅ CUDA доступна")
    try:
        _ = torch.zeros(1).cuda()
        print(f"✅ GPU ок: {torch.cuda.get_device_name(0)}")
    except Exception as e:
        print(f"⚠️ Ошибка инициализации GPU: {e}")
        return "cpu"
    return "cuda"


def main():
    # Отключаем прокси для localhost
    os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
    os.environ['no_proxy'] = 'localhost,127.0.0.1'

    # Подбираем устройство
    recommended = check_cuda_availability()
    cfg = get_config()
    if cfg.transcriber.device == "cuda" and recommended == "cpu":
        print("⚙️ Переключаю устройство в конфиге: cuda → cpu")
        update_config(**{'transcriber.device': 'cpu'})

    studio = WhisperRAGStudio()
    demo: gr.Blocks = build_interface(studio)

    # Ctrl+C → корректное закрытие БД
    def _sigint(_sig, _frm):
        print("\n🛑 Остановка... Закрываю БД")
        try:
            studio.db.close()
        finally:
            sys.exit(0)

    signal.signal(signal.SIGINT, _sigint)

    print("\n" + "=" * 60)
    print("🚀 Запуск Whisper RAG Studio")
    print("=" * 60)
    print(f"🖥️ Устройство: {studio.config.transcriber.device.upper()}")
    print(f"🎤 Модель: {studio.config.transcriber.model_name}")
    print(f"🔇 VAD: {'✓' if studio.config.transcriber.use_vad else '✗'}")
    print("=" * 60)

    demo.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=False,
        inbrowser=True,
        prevent_thread_lock=False,
    )


if __name__ == "__main__":
    main()

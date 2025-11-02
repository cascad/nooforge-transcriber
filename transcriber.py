"""
Транскрибатор с поддержкой Whisper и Faster-Whisper
"""
import os
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List
from app.config import get_config


class Transcriber:
    def __init__(self, config=None):
        if config is None:
            config = get_config().transcriber
        
        self.config = config
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Загрузка модели"""
        if self.config.use_faster_whisper:
            self._load_faster_whisper()
        else:
            self._load_whisper()
    
    def _load_faster_whisper(self):
        """Загрузка Faster-Whisper"""
        from faster_whisper import WhisperModel
        
        print(f"🔄 Загружаю Faster-Whisper '{self.config.model_name}'...")
        
        if self.config.model_path:
            self.model = WhisperModel(
                self.config.model_path,
                device=self.config.device,
                compute_type=self.config.compute_type,
                local_files_only=True
            )
        else:
            self.model = WhisperModel(
                self.config.model_name,
                device=self.config.device,
                compute_type=self.config.compute_type
            )
        
        print("✅ Faster-Whisper загружен")
    
    def _load_whisper(self):
        """Загрузка оригинального Whisper"""
        import whisper
        
        print(f"🔄 Загружаю Whisper '{self.config.model_name}'...")
        
        if self.config.model_path:
            self.model = whisper.load_model(
                self.config.model_name,
                download_root=self.config.model_path
            )
        else:
            self.model = whisper.load_model(self.config.model_name)
        
        print("✅ Whisper загружен")
    
    def extract_audio_from_video(self, video_path: str) -> Optional[str]:
        """Извлечение аудио из видео через ffmpeg"""
        output = tempfile.mktemp(suffix='.wav')
        
        print(f"🎬 Извлекаю аудио из видео...")
        
        try:
            cmd = [
                'ffmpeg', '-i', video_path, '-vn',
                '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
                '-y', output
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                print(f"❌ Ошибка ffmpeg: {result.stderr}")
                return None
            
            print(f"✅ Аудио извлечено")
            return output
            
        except FileNotFoundError:
            print("❌ ffmpeg не найден")
            return None
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return None
    
    def is_likely_hallucination(self, text: str, no_speech_prob: Optional[float] = None) -> bool:
        """Проверка на галлюцинацию"""
        if not self.config.filter_hallucinations:
            return False
        
        text_lower = text.lower().strip()
        
        for hallucination in self.config.hallucinations:
            if hallucination in text_lower:
                if no_speech_prob and no_speech_prob > 0.6:
                    return True
                if text_lower == hallucination:
                    return True
        
        return False
    
    def transcribe_file(self, file_path: str, progress_callback=None) -> Tuple[str, dict]:
        """
        Транскрибация файла
        
        Returns:
            (full_text, metadata)
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        # Определяем тип файла
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
        is_video = file_path.suffix.lower() in video_extensions
        
        # Извлекаем аудио если видео
        temp_audio = None
        if is_video:
            temp_audio = self.extract_audio_from_video(str(file_path))
            if temp_audio is None:
                raise Exception("Не удалось извлечь аудио из видео")
            audio_path = temp_audio
        else:
            audio_path = str(file_path)
        
        try:
            if progress_callback:
                progress_callback(0.1, "Транскрибация...")
            
            # Транскрибация
            if self.config.use_faster_whisper:
                full_text, metadata = self._transcribe_faster_whisper(audio_path, progress_callback)
            else:
                full_text, metadata = self._transcribe_whisper(audio_path, progress_callback)
            
            if progress_callback:
                progress_callback(1.0, "Готово!")
            
            return full_text, metadata
            
        finally:
            # Удаляем временный аудиофайл
            if temp_audio and os.path.exists(temp_audio):
                os.remove(temp_audio)
    
    def _transcribe_faster_whisper(self, audio_path: str, progress_callback=None) -> Tuple[str, dict]:
        """Транскрибация через Faster-Whisper"""
        segments, info = self.model.transcribe(
            audio_path,
            language=self.config.language,
            vad_filter=self.config.use_vad,
            condition_on_previous_text=False,
            vad_parameters=dict(threshold=self.config.vad_threshold) if self.config.use_vad else None
        )
        
        full_text = []
        filtered_count = 0
        total_segments = 0
        
        for segment in segments:
            total_segments += 1
            text = segment.text.strip()
            no_speech_prob = getattr(segment, 'no_speech_prob', None)
            
            # Фильтрация галлюцинаций
            if self.is_likely_hallucination(text, no_speech_prob):
                filtered_count += 1
                continue
            
            full_text.append(text)
            
            if progress_callback and total_segments % 10 == 0:
                progress_callback(0.1 + 0.8 * (total_segments / max(total_segments, 100)), 
                                f"Обработано сегментов: {total_segments}")
        
        metadata = {
            'duration': info.duration,
            'language': info.language,
            'total_segments': total_segments,
            'filtered_segments': filtered_count,
            'model': self.config.model_name
        }
        
        return "\n".join(full_text), metadata
    
    def _transcribe_whisper(self, audio_path: str, progress_callback=None) -> Tuple[str, dict]:
        """Транскрибация через оригинальный Whisper"""
        result = self.model.transcribe(
            audio_path,
            language=self.config.language,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            verbose=False
        )
        
        full_text = []
        filtered_count = 0
        
        for i, segment in enumerate(result.get('segments', [])):
            text = segment['text'].strip()
            no_speech_prob = segment.get('no_speech_prob', 0)
            
            # Фильтрация галлюцинаций
            if self.is_likely_hallucination(text, no_speech_prob):
                filtered_count += 1
                continue
            
            full_text.append(text)
            
            if progress_callback and i % 10 == 0:
                progress = 0.1 + 0.8 * (i / len(result['segments']))
                progress_callback(progress, f"Обработано сегментов: {i}")
        
        metadata = {
            'duration': result.get('duration', 0),
            'language': result.get('language', self.config.language),
            'total_segments': len(result.get('segments', [])),
            'filtered_segments': filtered_count,
            'model': self.config.model_name
        }
        
        return "\n".join(full_text), metadata


if __name__ == "__main__":
    # Тест транскрибатора
    transcriber = Transcriber()
    
    # Пример использования
    # text, metadata = transcriber.transcribe_file("audio.mp3")
    # print(f"Text: {text[:100]}...")
    # print(f"Metadata: {metadata}")
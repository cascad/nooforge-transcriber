"""
Нарезка текста на чанки для RAG
"""
from typing import List
from app.config import get_config


class TextChunker:
    def __init__(self, config=None):
        if config is None:
            config = get_config().chunker
        
        self.chunk_size = config.chunk_size
        self.chunk_overlap = config.chunk_overlap
        self.separator = config.separator
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Нарезка текста на чанки с перекрытием
        
        Args:
            text: исходный текст
            
        Returns:
            список чанков
        """
        if not text or not text.strip():
            return []
        
        # Разбиваем по разделителю (параграфы)
        paragraphs = text.split(self.separator)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para)
            
            # Если параграф сам больше chunk_size
            if para_size > self.chunk_size:
                # Сохраняем текущий чанк
                if current_chunk:
                    chunks.append(self.separator.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                
                # Разбиваем большой параграф на куски
                chunks.extend(self._split_large_paragraph(para))
                continue
            
            # Если добавление параграфа превысит размер
            if current_size + para_size > self.chunk_size and current_chunk:
                # Сохраняем текущий чанк
                chunks.append(self.separator.join(current_chunk))
                
                # Создаем перекрытие (overlap)
                overlap_text = self._create_overlap(current_chunk)
                current_chunk = [overlap_text, para] if overlap_text else [para]
                current_size = len(overlap_text) + para_size if overlap_text else para_size
            else:
                # Добавляем к текущему чанку
                current_chunk.append(para)
                current_size += para_size + len(self.separator)
        
        # Добавляем последний чанк
        if current_chunk:
            chunks.append(self.separator.join(current_chunk))
        
        return chunks
    
    def _split_large_paragraph(self, paragraph: str) -> List[str]:
        """Разбивка большого параграфа на куски по предложениям"""
        # Простая разбивка по предложениям
        sentences = paragraph.replace('! ', '!|').replace('? ', '?|').replace('. ', '.|').split('|')
        
        chunks = []
        current = []
        current_size = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sent_size = len(sentence)
            
            if current_size + sent_size > self.chunk_size and current:
                chunks.append(' '.join(current))
                # Оставляем последнее предложение для перекрытия
                if self.chunk_overlap > 0:
                    current = [current[-1], sentence]
                    current_size = len(current[-1]) + sent_size
                else:
                    current = [sentence]
                    current_size = sent_size
            else:
                current.append(sentence)
                current_size += sent_size
        
        if current:
            chunks.append(' '.join(current))
        
        return chunks
    
    def _create_overlap(self, chunks: List[str]) -> str:
        """Создание текста перекрытия из последних частей чанка"""
        if not chunks or self.chunk_overlap <= 0:
            return ""
        
        # Берем последние элементы пока не достигнем overlap размера
        overlap_parts = []
        overlap_size = 0
        
        for chunk in reversed(chunks):
            if overlap_size + len(chunk) <= self.chunk_overlap:
                overlap_parts.insert(0, chunk)
                overlap_size += len(chunk) + len(self.separator)
            else:
                break
        
        return self.separator.join(overlap_parts) if overlap_parts else ""


if __name__ == "__main__":
    # Тест чанкера
    chunker = TextChunker()
    
    test_text = """
Это первый параграф текста. Он содержит несколько предложений. Они будут использованы для теста.

Это второй параграф. Он тоже содержит текст.

Это третий параграф с очень длинным текстом, который будет разбит на несколько частей, потому что он превышает максимальный размер чанка и нужно его разделить на более мелкие части для обработки.

Четвертый параграф короткий.

Пятый параграф тоже короткий.
    """.strip()
    
    chunks = chunker.chunk_text(test_text)
    
    print(f"Всего чанков: {len(chunks)}\n")
    for i, chunk in enumerate(chunks, 1):
        print(f"Чанк {i} ({len(chunk)} символов):")
        print(chunk[:100] + "..." if len(chunk) > 100 else chunk)
        print("-" * 50)
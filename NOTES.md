**Важно:** Также установите ffmpeg для обработки видео:
- **Ubuntu/Debian:** `sudo apt-get install ffmpeg`
- **macOS:** `brew install ffmpeg`
- **Windows:** Скачайте с https://ffmpeg.org/

python 3.10-3.12, тестил под win 3.12

python -m pip uninstall torch torchaudio
python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128

Вот так можно скачать модельку
```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Systran/faster-whisper-large-v3",
    local_dir="./models/models--Systran--faster-whisper-large-v3",
    local_dir_use_symlinks=False  # чтобы не было симлинков, только файлы
)
```

тут положить модельку
.\models\models--Systran--faster-whisper-large-v3\snapshots\edaa852ec7e145841d8ffdb056a99866b5f0a478

тут база лежит
.\data

так затестить и пересобрать Dockerfile
docker run -it --rm nvidia/cuda:12.8.0-devel-ubuntu22.04
FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive TZ=UTC

# Включаем universe репозиторий (он уже включён по умолчанию, но на всякий)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        software-properties-common \
        ca-certificates \
        wget \
        git \
        curl \
        ffmpeg \
        libavcodec-extra \
        vim \
    && add-apt-repository universe -y && \
    apt-get update

# Устанавливаем Python 3.11 из официальных репозиториев Ubuntu 22.04
RUN apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-venv \
        python3.11-dev \
        python3-distutils \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Настраиваем альтернативы
RUN ln -sf /usr/bin/python3.11 /usr/bin/python3 && \
    ln -sf /usr/bin/pip3.11 /usr/bin/pip3

# Обновляем pip
RUN python3 -m pip install --no-cache-dir --upgrade pip

WORKDIR /app
COPY req.txt requirements.txt

# Устанавливаем torch из кастомного индекса
RUN python3 -m pip install --no-cache-dir torch==2.9.0+cu128 torchaudio==2.9.0+cu128 \
    --extra-index-url https://download.pytorch.org/whl/cu128

# Остальные зависимости
RUN grep -v "torch\|torchaudio" requirements.txt > requirements-clean.txt && \
    python3 -m pip install --no-cache-dir -r requirements-clean.txt

CMD ["python3", "-c", "print('Ready.')"]
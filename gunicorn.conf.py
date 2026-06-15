import os

# Gunicorn слушает внутри контейнера только локальный HTTP для Caddy,
# поэтому здесь оставляем bind на внутренний порт приложения.
bind = "0.0.0.0:8000"

# Количество workers и threads подобрано так, чтобы генератор не блокировался
# на фоновых запросах и одновременно мог принимать несколько операций.
workers = 5
threads = 6

# Большие EXE/MSI могут загружаться с GitHub Actions очень медленно,
# особенно когда runner находится далеко от сервера.
# Увеличиваем timeout, чтобы Gunicorn не убивал worker во время длинного upload.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "1800"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "120"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "30"))
activate_base = True

# Явно указываем WSGI-приложение проекта.
wsgi_app = "rdgen.wsgi.application"

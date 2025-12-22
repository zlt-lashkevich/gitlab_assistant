# Инструкции по запуску и настройке GitLab Assistant

Это руководство для настройки и запуска Telegram-бота **GitLab Assistant** на локальном компьютере или с помощью Docker

---

## Часть 1: Получение необходимых токенов

Для работы бота потребуются следующие токены:

### 1. Telegram Bot Token

1.  Откройте Telegram и найдите бота **[@BotFather](https://t.me/botfather)**.
2.  Отправьте ему команду `/newbot`.
3.  Следуйте инструкциям, чтобы задать имя и юзернейм для вашего бота.
4.  В конце **@BotFather** пришлет вам токен. **Скопируйте его.**

### 2. GitLab Personal Access Token (PAT)

1.  Войдите в свой аккаунт GitLab.
2.  Перейдите в **User Settings** → **Access Tokens**.
3.  Нажмите **Add new token**.
4.  Задайте имя токену (например, `gitlab-assistant-token`).
5.  Выберите права (scopes). Для работы бота необходимы как минимум:
    *   `api` (полный доступ к API)
    *   `read_repository` (чтение репозиториев)
6.  Нажмите **Create personal access token**.
7.  **Скопируйте токен.** После того как вы покинете страницу, он больше не будет доступен.

### 3. GitHub Personal Access Token (PAT)

1.  Войдите в свой аккаунт GitHub.
2.  Перейдите в **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**.
3.  Нажмите **Generate new token** → **Generate new token (classic)**.
4.  Задайте имя токену (например, `gitlab-assistant-token`).
5.  Выберите права (scopes). Для работы бота необходимы:
    *   `repo` (полный доступ к репозиториям)
    *   `notifications` (доступ к уведомлениям)
6.  Нажмите **Generate token**.
7.  **Скопируйте токен.**

---

## Часть 2: Запуск проекта

Проект может быть запущен двумя способами: локально с помощью Python или с помощью Docker

### Локальный запуск

1.  **Клонируйте репозиторий:**

    ```bash
    git clone <repository-url>
    cd gitlab-assistant
    ```

2.  **Создайте и активируйте виртуальное окружение:**

    ```bash
    # Для Linux / macOS
    python3 -m venv venv
    source venv/bin/activate

    # Для Windows
    python -m venv venv
    venv\Scripts\activate
    ```

3.  **Установите зависимости:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Настройте переменные окружения:**

    Скопируйте файл с примером конфигурации:

    ```bash
    cp .env.example .env
    ```

    Откройте файл `.env` в текстовом редакторе и вставьте ваши токены, полученные в Части 1:

    ```dotenv
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN=сюда_вставьте_токен_вашего_бота

    # GitLab Configuration
    GITLAB_URL=https://gitlab.com
    GITLAB_PRIVATE_TOKEN=сюда_вставьте_ваш_gitlab_токен

    # GitHub Configuration
    GITHUB_TOKEN=сюда_вставьте_ваш_github_токен

    # Database Configuration (для локального запуска можно оставить SQLite)
    DATABASE_URL=sqlite+aiosqlite:///./gitlab_assistant.db
    ```

5.  **Запустите бота:**

    ```bash
    python main.py
    ```

    Если все настроено правильно, то в консоли появятся сообщения о запуске бота. Теперь бота можно найти в Telegram и отправить ему команду `/start`.

### Запуск с помощью Docker


1.  **Клонируйте репозиторий** как в шаге 1 предыдущего варианта

2.  **Настройте переменные окружения:**

    Создайте файл `.env` по аналогии с 4 пунктом предыдущего варианта

    Для использования PostgreSQL, который идет в комплекте с `docker-compose.yml`, измените `DATABASE_URL`:

    ```dotenv
    DATABASE_URL=postgresql+asyncpg://gitlab_assistant:secure_password_here@postgres:5432/gitlab_assistant
    ```

3.  **Запустите Docker Compose:**

    В терминале в корневой папке проекта необходмо выполнить команду:

    ```bash
    docker-compose up --build -d
    ```

    Эта команда соберет образ для бота, скачает образ PostgreSQL и запустит оба контейнера в фоновом режиме.

4.  **Проверка статуса и логов:**

    ```bash
    # Проверить статус контейнеров
    docker-compose ps

    # Посмотреть логи бота в реальном времени
    docker-compose logs -f bot
    ```

5.  **Остановка:**

    ```bash
    docker-compose down
    ```

---

## Часть 3: Использование бота

После запуска бота найдите его в Telegram и начните диалог.

1.  **Начало работы:**
    Отправьте команду `/start`. Бот поприветствует вас и зарегистрирует в системе.

2.  **Установка токенов (если не сделали через `.env`):**
    Вы можете установить или обновить токены прямо через чат с ботом. **Сообщения с токенами будут автоматически удалены** для безопасности.

    ```
    /set_gitlab_token <ваш_gitlab_токен>
    /set_github_token <ваш_github_токен>
    ```

3.  **Просмотр статуса:**
    Команда `/status` покажет ваш ID, установлены ли токены и количество активных подписок.

4.  **Получение справки:**
    Команда `/help` выведет список всех доступных команд.

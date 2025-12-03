# GitLab Assistant 

Пользовательсоке описание Telegram-бота для отслеживания событий в GitLab и GitHub проектах

## Возможности

- Уведомления о статусе CI/CD пайплайнов
- Упоминания в Merge Requests / Pull Requests
- Назначение ревьюверов
- Обновления документации и Wiki
- Поддержка GitLab и GitHub
- Гибкая настройка подписок
- Безопасное хранение токенов

## Архитектура

```
gitlab-assistant/
├── src/                          # Исходный код
│   ├── bot/                      # Telegram бот
│   │   ├── bot.py               # Главный файл бота
│   │   ├── handlers.py          # Базовые обработчики команд
│   │   ├── subscription_handlers.py  # Обработчики подписок
│   │   ├── keyboards.py         # Inline клавиатуры
│   │   └── states.py            # FSM состояния
│   ├── database/                 # База данных
│   │   ├── models.py            # SQLAlchemy модели
│   │   └── database.py          # Работа с БД
│   ├── gitlab_api/               # GitLab API
│   │   └── client.py            # Асинхронный клиент
│   ├── github_api/               # GitHub API
│   │   └── client.py            # Асинхронный клиент
│   ├── webhook/                  # Webhook сервер
│   │   ├── server.py            # HTTP сервер
│   │   ├── handlers.py          # Обработчики событий
│   │   ├── notifier.py          # Отправка уведомлений
│   │   └── manager.py           # Управление webhooks
│   └── config.py                 # Конфигурация
├── tests/                        # Тесты
│   └── test_webhook.py           # Тесты обработчиков
├── main.py                       # Точка входа
├── requirements.txt              # Python зависимости, то что нужно предустановить
├── .gitignore                    # Git ignore
└── docs/                         # Документация, README
```

![img.png](gitlab_assistant.png)

```mermaid
%%{init: {"theme":"base","themeVariables":{"textColor":"#0B3D91","primaryTextColor":"#0B3D91","secondaryTextColor":"#0B3D91","tertiaryTextColor":"#0B3D91"}}}%%
flowchart TD
  U[Пользователь Telegram]
  TG[Telegram API]

  subgraph BOT["Бот (aiogram)"]
    direction TB
    B[Bot]
    FSM[FSM состояния]
    KB[Inline-клавиатуры]
  end

  subgraph DATA["Хранилище"]
    direction TB
    DB[(БД: subscriptions, users, projects)]
  end

  subgraph APIs["Клиенты API (aiohttp)"]
    direction TB
    GL[GitLab API]
    GH[GitHub API]
  end

  subgraph WEBHOOK["Webhook-сервер"]
    direction TB
    Srv[HTTP сервер]
    H[Обработчики событий]
    Mgr[Управление webhooks]
    Ntf[Notifier]
  end

  U --> TG --> B
  B --> FSM
  B --> KB
  B <--> DB
  H <--> DB
  B --> GL
  B --> GH
  B --> Mgr
  Mgr --> GL
  Mgr --> GH
  GL --> Srv
  GH --> Srv
  Srv --> H
  H --> Ntf
  Ntf --> TG --> U
```

##  Использование бота

### Основные команды

- `/start` — Начало работы с ботом
- `/help` — Справка по командам
- `/status` — Текущий статус и подписки
- `/subscribe` — Подписка на проекты GitLab/GitHub
- `/unsubscribe` — Отписка от проектов
- `/list_subscriptions` — Все активные подписки
- `/set_gitlab_token` — Установка GitLab токена
- `/set_github_token` — Установка GitHub токена
PS. оба токены должны быть созданы пользователем так, чтобы был полный доступ к API и репозиторию (Lab) / уведомлениям (Hub)
- `/notifications`  выбрать, какие будут приходить уведомления/упоминания из описанных выше (здесь будут реализованы кнопки с разными вариантами выбора подписок и отменой)

### Подробнее про подписки и уведомления:
**Finite State Machine:** Для управления интерактивными диалогами подписки и отписки будет внедрена система состояний (FSM) с использованием `aiogram.fsm`
- **Состояния:** Созданы две группы состояний:
      - `SubscriptionStates` — для процесса подписки (выбор платформы, проекта, событий, подтверждение).
      - `UnsubscriptionStates` — для процесса отписки (выбор подписки, подтверждение).
- **Хранилище состояний:** В качестве хранилища используется `MemoryStorage`, что идеально подходит для разработки и тестирования.

**`/subscribe`:** Будет запускать пошаговый процесс подписки:
  1. **Выбор платформы:** Бот предлагает выбрать GitLab или GitHub с помощью inline-клавиатуры
  2. **Выбор проекта:** После выбора платформы бот запрашивает список проектов пользователя и отображает их в виде пагинированной inline-клавиатуры.
  3. **Выбор событий:** Пользователь может выбрать интересующие его события (pipelines, merge requests и т.д.) с помощью интерактивной клавиатуры.
  4. **Подтверждение:** Бот выводит сводную информацию и запрашивает подтверждение.
  5. **Создание/обновление подписки:** В базе данных создается новая или обновляется существующая подписка.
 
**`/unsubscribe`:**  Команда для отписки от проектов, дублирует функционал подписки, но в конце подписка удаляется из базы данных.

 **`/cancel`:** В любой момент процесса пользователь может нажать кнопку "Отмена", чтобы прервать операцию.


### Интеграция с API 
- Получение списка проектов
- Управление webhooks
- Получение информации о MR, pipelines, issues и PR, workflows, issues для GitLab/GitHub
- Асинхронные запросы

### Webhook-сервер
Необходим для того, чтобы ловить события из git систем и пересылать их дальше в нужном нам виде и только тем, кто на них подписан
GitLab/GitHub → webhook-сервер → Telegram

**Возможности:**
- Прием событий от GitLab и GitHub
- Обработка различных типов событий
- Фильтрация по подпискам
- Форматирование уведомлений
- Health check endpoint

### Типы событий, которые поддерживает этот самостоятельный HTTP-сервер (webhook)

### GitLab

| Событие | Описание | Состояние                |
|---------|----------|--------------------------|
|  Pipeline | Изменения статуса CI/CD пайплайнов | success, failed, running |
|  Merge Request | События в merge requests | opened, merged, closed   |
|  Issue | События в issues | opened, closed, updated  |
|  Wiki | Обновления wiki | created, updated         |
|  Комментарии | Новые комментарии | Note, Comment            |

### GitHub

| Событие | Описание | Состояние        |
|-------|----------|------------------|
|  Workflow | Изменения в GitHub Actions | success, failure |
| Pull Request | События в pull requests | opened, merged, closed|
| Issue | События в issues | opened, closed |
| Комментарии | Новые комментарии | issue, PR |

---

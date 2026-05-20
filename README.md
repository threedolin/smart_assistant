# Smart Assistant

**Smart Assistant** — это однофайловый локальный AI-помощник на Python с графическим интерфейсом PyQt6.  
Приложение работает через локальную модель **Ollama** и не требует OpenAI API.

## Возможности

- чат с локальной LLM через Ollama;
- модель по умолчанию: `llama3.2`;
- графический интерфейс на PyQt6;
- быстрые команды:
  - `привет`
  - `открой браузер`
  - `видео <запрос>`
  - `монетку`
  - `вики <запрос>`
  - `погода в <город>`
  - `очисти историю`
- всё приложение находится в одном файле `app.py`.

## Требования

- Python 3.10+
- Ollama
- установленная модель `llama3.2`

## Установка

1. Склонируйте репозиторий:

```bash
git clone https://github.com/USERNAME/smart-helper-ollama.git
cd smart-helper-ollama
```

2. Создайте виртуальное окружение:

```bash
python -m venv .venv
```

3. Активируйте окружение.

Для Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Для macOS/Linux:

```bash
source .venv/bin/activate
```

4. Установите зависимости:

```bash
pip install -r requirements.txt
```

5. Установите модель Ollama:

```bash
ollama pull llama3.2
```

6. Запустите Ollama:

```bash
ollama serve
```

Если команда пишет, что порт уже занят, значит Ollama уже запущена.

7. Запустите приложение:

```bash
python app.py
```

## Как поменять модель

По умолчанию используется:

```python
DEFAULT_MODEL = "llama3.2"
```

Можно заменить на другую установленную модель Ollama, например:

```python
DEFAULT_MODEL = "mistral"
```

После этого модель нужно установить:

```bash
ollama pull mistral
```

## Структура проекта

```text
smart-helper-ollama/
├── app.py
├── requirements.txt
├── README.md
└── .gitignore
```

## Назначение проекта

Проект можно использовать как пет-проект для портфолио: он показывает работу с локальными LLM, GUI-приложением на Python и интеграцией с Ollama API.

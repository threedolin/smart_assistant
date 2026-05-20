"""
Smart Helper — one-file Ollama version

Запуск:
    pip install PyQt6 requests
    ollama pull llama3.2
    ollama serve
    python smart_helper_ollama_onefile.py

Что умеет:
- чат с локальной моделью Ollama через http://localhost:11434/api/chat
- быстрые команды: привет, браузер, видео, монетка, вики, погода, очистить историю
- простое PyQt6-окно без .ui-файлов и без отдельных модулей
"""

from __future__ import annotations

import json
import random
import sys
import threading
import traceback
import urllib.parse
import webbrowser
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Callable, Optional

import requests
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


APP_TITLE = "Smart Helper — Ollama"
DEFAULT_MODEL = "llama3.2"
DEFAULT_OLLAMA_URL = "http://localhost:11434"

SYSTEM_PROMPT = (
    "Ты — русскоязычный голосовой/текстовый помощник Smart Helper. "
    "Отвечай понятно, по делу и на русском языке. "
    "Если пользователь просит план или инструкцию, давай пошаговый ответ."
)


@dataclass
class AssistantConfig:
    model: str = DEFAULT_MODEL
    ollama_url: str = DEFAULT_OLLAMA_URL
    temperature: float = 0.3
    max_history_messages: int = 12


class OllamaClient:
    def __init__(self, config: AssistantConfig):
        self.config = config
        self.history: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def reset_history(self) -> None:
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def chat(self, user_text: str) -> str:
        self.history.append({"role": "user", "content": user_text})
        self._trim_history()

        url = self.config.ollama_url.rstrip("/") + "/api/chat"
        payload = {
            "model": self.config.model.strip() or DEFAULT_MODEL,
            "messages": self.history,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
            },
        }

        try:
            response = requests.post(url, json=payload, timeout=180)
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                "Не удалось подключиться к Ollama. Проверь, что Ollama запущена: "
                "ollama serve"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                "Ollama слишком долго отвечает. Попробуй более короткий вопрос "
                "или закрой лишние программы."
            ) from exc

        if response.status_code == 404:
            raise RuntimeError(
                f"Модель '{self.config.model}' не найдена. Выполни команду: "
                f"ollama pull {self.config.model}"
            )

        if not response.ok:
            raise RuntimeError(
                f"Ошибка Ollama API {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        answer = data.get("message", {}).get("content", "").strip()
        if not answer:
            answer = "Модель вернула пустой ответ. Попробуй переформулировать вопрос."

        self.history.append({"role": "assistant", "content": answer})
        self._trim_history()
        return answer

    def _trim_history(self) -> None:
        system = self.history[:1]
        rest = self.history[1:]
        if len(rest) > self.config.max_history_messages:
            rest = rest[-self.config.max_history_messages :]
        self.history = system + rest


class OptionalSpeaker:
    """Необязательная озвучка ответа. Если pyttsx3 не установлен, приложение работает без неё."""

    def __init__(self) -> None:
        self.available = False
        self._engine = None
        self._lock = threading.Lock()
        try:
            import pyttsx3  # type: ignore

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", 150)
            self.available = True
        except Exception:
            self.available = False

    def say(self, text: str) -> None:
        if not self.available or self._engine is None:
            return

        def worker() -> None:
            with self._lock:
                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()


class CommandProcessor:
    def __init__(self, on_clear_history: Callable[[], None]):
        self.on_clear_history = on_clear_history
        self.commands: list[tuple[list[str], Callable[[str], str]]] = [
            (["привет", "здравствуй", "здравствуйте"], self._hello),
            (["открой браузер", "запусти браузер", "браузер"], self._open_browser),
            (["видео", "найди видео", "ютуб", "youtube"], self._open_video),
            (["монетку", "подбрось монетку", "орел или решка"], self._flip_coin),
            (["вики", "википедия", "найди в википедии"], self._wiki),
            (["погода", "погода в"], self._weather),
            (["очисти историю", "сбрось историю", "новый чат"], self._clear_history),
        ]

    def try_execute(self, text: str) -> Optional[str]:
        normalized = self._normalize(text)

        # Сначала проверяем явные вхождения, чтобы команды с параметрами работали надёжно.
        for examples, action in self.commands:
            for example in examples:
                if example in normalized:
                    return action(text)

        # Потом мягкое совпадение для коротких команд.
        best_score = 0.0
        best_action: Optional[Callable[[str], str]] = None
        for examples, action in self.commands:
            for example in examples:
                score = SequenceMatcher(None, normalized, example).ratio()
                if score > best_score:
                    best_score = score
                    best_action = action

        if best_score >= 0.78 and best_action:
            return best_action(text)
        return None

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().replace("ё", "е").strip().split())

    def _hello(self, _: str) -> str:
        return "Привет! Я Smart Helper на Ollama. Напиши вопрос или команду."

    def _open_browser(self, _: str) -> str:
        webbrowser.open("https://www.google.com")
        return "Открыл браузер."

    def _open_video(self, text: str) -> str:
        query = self._remove_command_words(
            text,
            ["видео", "найди видео", "ютуб", "youtube", "найди", "покажи"],
        )
        if not query:
            query = "интересное видео"
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
        webbrowser.open(url)
        return f"Открыл поиск YouTube по запросу: {query}"

    def _flip_coin(self, _: str) -> str:
        return random.choice(["Выпал орёл.", "Выпала решка."])

    def _wiki(self, text: str) -> str:
        topic = self._remove_command_words(
            text,
            ["вики", "википедия", "найди в википедии", "найди", "что такое", "кто такой"],
        )
        if not topic:
            return "Напиши тему после команды. Например: вики искусственный интеллект"

        title = urllib.parse.quote(topic.replace(" ", "_"))
        url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{title}"
        try:
            response = requests.get(url, timeout=15, headers={"User-Agent": APP_TITLE})
            if response.status_code == 404:
                return f"Не нашёл статью в Википедии по теме: {topic}"
            response.raise_for_status()
            data = response.json()
            extract = data.get("extract", "").strip()
            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            if not extract:
                return f"Статья найдена, но краткое описание пустое: {page_url}"
            if page_url:
                return extract[:1200] + f"\n\nИсточник: {page_url}"
            return extract[:1200]
        except Exception as exc:
            return f"Не получилось получить данные из Википедии: {exc}"

    def _weather(self, text: str) -> str:
        city = self._remove_command_words(text, ["погода", "погода в", "какая", "сейчас"])
        if not city:
            return "Напиши город после команды. Например: погода в Москве"

        url = "https://wttr.in/" + urllib.parse.quote(city) + "?format=3&lang=ru"
        try:
            response = requests.get(url, timeout=15, headers={"User-Agent": APP_TITLE})
            response.raise_for_status()
            return response.text.strip()
        except Exception as exc:
            return f"Не получилось получить погоду: {exc}"

    def _clear_history(self, _: str) -> str:
        self.on_clear_history()
        return "История диалога очищена."

    def _remove_command_words(self, text: str, words: list[str]) -> str:
        result = self._normalize(text)
        for word in sorted(words, key=len, reverse=True):
            result = result.replace(word, " ")
        return " ".join(result.split()).strip()


class ChatWorker(QObject):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, client: OllamaClient, text: str):
        super().__init__()
        self.client = client
        self.text = text

    def run(self) -> None:
        try:
            answer = self.client.chat(self.text)
            self.finished.emit(answer)
        except Exception as exc:
            details = str(exc)
            if not details:
                details = traceback.format_exc()
            self.failed.emit(details)


class MessageBubble(QLabel):
    def __init__(self, text: str, is_user: bool):
        super().__init__(text)
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(220)
        self.setMaximumWidth(720)
        self.setFont(QFont("Arial", 11))
        if is_user:
            self.setStyleSheet(
                "QLabel { background: #D7F8C6; padding: 10px; border-radius: 12px; }"
            )
        else:
            self.setStyleSheet(
                "QLabel { background: #F1F1F1; padding: 10px; border-radius: 12px; }"
            )


class SmartHelperWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = AssistantConfig()
        self.client = OllamaClient(self.config)
        self.speaker = OptionalSpeaker()
        self.commands = CommandProcessor(on_clear_history=self.client.reset_history)
        self.current_thread: Optional[QThread] = None
        self.current_worker: Optional[ChatWorker] = None

        self.setWindowTitle(APP_TITLE)
        self.resize(900, 680)
        self._build_ui()
        self._build_menu()
        self._add_bot_message(
            "Привет! Я Smart Helper на Ollama. "
            "Спроси что-нибудь или напиши команду: «вики Python», «погода в Москве», «видео коты», «монетку»."
        )

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("Помощь")
        about_action = QAction("Как запустить Ollama", self)
        about_action.triggered.connect(self._show_ollama_help)
        menu.addAction(about_action)

    def _build_ui(self) -> None:
        root = QWidget()
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Модель:"))
        self.model_box = QComboBox()
        self.model_box.setEditable(True)
        self.model_box.addItems(["llama3.2", "llama3.1", "mistral", "qwen2.5", "gemma3"])
        self.model_box.setCurrentText(DEFAULT_MODEL)
        self.model_box.currentTextChanged.connect(self._model_changed)
        top_layout.addWidget(self.model_box, stretch=2)

        top_layout.addWidget(QLabel("Ollama URL:"))
        self.url_input = QLineEdit(DEFAULT_OLLAMA_URL)
        self.url_input.textChanged.connect(self._url_changed)
        top_layout.addWidget(self.url_input, stretch=3)

        top_layout.addWidget(QLabel("История:"))
        self.history_spin = QSpinBox()
        self.history_spin.setRange(2, 40)
        self.history_spin.setValue(self.config.max_history_messages)
        self.history_spin.valueChanged.connect(self._history_changed)
        top_layout.addWidget(self.history_spin)

        self.tts_checkbox = QCheckBox("озвучивать")
        self.tts_checkbox.setEnabled(self.speaker.available)
        if not self.speaker.available:
            self.tts_checkbox.setToolTip("Для озвучки установи: pip install pyttsx3")
        top_layout.addWidget(self.tts_checkbox)
        main_layout.addLayout(top_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages_layout.setSpacing(8)
        self.scroll_area.setWidget(self.messages_widget)
        main_layout.addWidget(self.scroll_area, stretch=1)

        bottom_layout = QHBoxLayout()
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Введите сообщение...")
        self.input_line.returnPressed.connect(self._send_message)
        bottom_layout.addWidget(self.input_line, stretch=1)

        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self._send_message)
        bottom_layout.addWidget(self.send_button)

        self.clear_button = QPushButton("Очистить")
        self.clear_button.clicked.connect(self._clear_chat)
        bottom_layout.addWidget(self.clear_button)

        main_layout.addLayout(bottom_layout)
        self.setCentralWidget(root)

    def _show_ollama_help(self) -> None:
        QMessageBox.information(
            self,
            "Запуск Ollama",
            "1. Установи Ollama\n"
            "2. Выполни: ollama pull llama3.2\n"
            "3. Запусти сервер: ollama serve\n"
            "4. Запусти этот файл: python smart_helper_ollama_onefile.py",
        )

    def _model_changed(self, model: str) -> None:
        self.config.model = model.strip() or DEFAULT_MODEL

    def _url_changed(self, url: str) -> None:
        self.config.ollama_url = url.strip() or DEFAULT_OLLAMA_URL

    def _history_changed(self, value: int) -> None:
        self.config.max_history_messages = value
        self.client._trim_history()

    def _send_message(self) -> None:
        text = self.input_line.text().strip()
        if not text:
            return
        self.input_line.clear()
        self._add_user_message(text)

        command_answer = self.commands.try_execute(text)
        if command_answer is not None:
            self._add_bot_message(command_answer)
            self._speak_if_needed(command_answer)
            return

        self._set_busy(True)
        self._add_bot_message("Думаю...")
        thinking_bubble = self.messages_layout.itemAt(self.messages_layout.count() - 1).layout().itemAt(0).widget()

        self.current_thread = QThread()
        self.current_worker = ChatWorker(self.client, text)
        self.current_worker.moveToThread(self.current_thread)
        self.current_thread.started.connect(self.current_worker.run)
        self.current_worker.finished.connect(lambda answer: self._handle_answer(answer, thinking_bubble))
        self.current_worker.failed.connect(lambda error: self._handle_answer("Ошибка: " + error, thinking_bubble))
        self.current_worker.finished.connect(self.current_thread.quit)
        self.current_worker.failed.connect(self.current_thread.quit)
        self.current_thread.finished.connect(self.current_worker.deleteLater)
        self.current_thread.finished.connect(self.current_thread.deleteLater)
        self.current_thread.finished.connect(lambda: self._set_busy(False))
        self.current_thread.start()

    def _handle_answer(self, answer: str, bubble: QLabel) -> None:
        bubble.setText(answer)
        self._scroll_to_bottom()
        self._speak_if_needed(answer)

    def _speak_if_needed(self, text: str) -> None:
        if self.tts_checkbox.isChecked():
            self.speaker.say(text)

    def _clear_chat(self) -> None:
        self.client.reset_history()
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item.layout():
                layout = item.layout()
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
            elif item.widget():
                item.widget().deleteLater()
        self._add_bot_message("Чат очищен. История Ollama сброшена.")

    def _add_user_message(self, text: str) -> None:
        self._add_message(text, is_user=True)

    def _add_bot_message(self, text: str) -> None:
        self._add_message(text, is_user=False)

    def _add_message(self, text: str, is_user: bool) -> None:
        row = QHBoxLayout()
        bubble = MessageBubble(text, is_user=is_user)
        if is_user:
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch(1)
        self.messages_layout.addLayout(row)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        QApplication.processEvents()
        bar = self.scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _set_busy(self, busy: bool) -> None:
        self.send_button.setEnabled(not busy)
        self.input_line.setEnabled(not busy)
        if not busy:
            self.input_line.setFocus()


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    window = SmartHelperWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

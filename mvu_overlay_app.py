"""
MVU VRAM Overlay Application.

Этот модуль представляет собой независимое приложение PyQt6, отображающее
потребление VRAM поверх всех окон. Предназначен для запуска как подпроцесс
из ComfyUI, но может работать и автономно.

Author: MVU
License: MIT
"""

import sys
import time
import logging
import argparse
import psutil
from typing import Optional

from pynvml import (
    nvmlInit,
    nvmlShutdown,
    nvmlDeviceGetHandleByIndex,
    nvmlDeviceGetMemoryInfo,
    NVMLError
)

from PyQt6.QtWidgets import QApplication, QWidget, QLabel
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSlot, QObject
from PyQt6.QtGui import QFont, QColor, QPalette, QMouseEvent


# --- КОНФИГУРАЦИЯ (SETTINGS) ---
class AppConfig:
    """Конфигурация приложения и константы."""
    # Визуальные настройки
    VRAM_TEXT_COLOR: str = "#32CD32"
    FONT_FAMILY: str = "Segoe UI"
    FONT_SIZE: int = 14
    FONT_WEIGHT: QFont.Weight = QFont.Weight.Bold
    
    # Позиционирование
    RIGHT_MARGIN: int = 130
    BOTTOM_MARGIN: int = 85
    
    # Логика обновления
    POLL_INTERVAL_MS: int = 500
    PROCESS_CHECK_INTERVAL_MS: int = 3000
    
    # Имя процесса для мониторинга (если PID не передан)
    TARGET_PROCESS_NAME: str = "python"
    TARGET_CMDLINE_KEYWORD: str = "main.py"
    
    # Логирование
    LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO, format=AppConfig.LOG_FORMAT)
logger = logging.getLogger("MVU_Overlay")


# --- MODEL (Работа с данными) ---
class VramMonitorModel:
    """
    Model: Отвечает за взаимодействие с драйвером NVIDIA через NVML.
    """
    def __init__(self) -> None:
        self._handle = None
        self._initialized: bool = False

    def initialize(self) -> None:
        """Инициализирует NVML и получает дескриптор устройства."""
        try:
            nvmlInit()
            # Берем первую GPU (index 0). При необходимости можно расширить.
            self._handle = nvmlDeviceGetHandleByIndex(0)
            self._initialized = True
            logger.info("NVML успешно инициализирован.")
        except NVMLError as error:
            logger.error(f"Ошибка инициализации NVML: {error}")
            self._initialized = False

    def get_free_memory_mb(self) -> Optional[int]:
        """Возвращает количество свободной VRAM в мегабайтах."""
        if not self._initialized or not self._handle:
            return None

        try:
            mem_info = nvmlDeviceGetMemoryInfo(self._handle)
            return mem_info.free // (1024 ** 2)
        except NVMLError as error:
            logger.warning(f"Ошибка чтения памяти GPU: {error}")
            return None

    def shutdown(self) -> None:
        """Корректно завершает работу с NVML."""
        if self._initialized:
            try:
                nvmlShutdown()
                logger.info("NVML ресурсы освобождены.")
            except NVMLError as error:
                logger.error(f"Ошибка при завершении NVML: {error}")


class ProcessMonitorModel:
    """
    Model: Отвечает за проверку существования родительского процесса ComfyUI.
    """
    def __init__(self, target_pid: Optional[int] = None) -> None:
        self.target_pid = target_pid

    def is_alive(self) -> bool:
        """
        Проверяет, жив ли целевой процесс.
        Если PID передан явно - проверяет его.
        Если нет - ищет процесс по сигнатуре командной строки.
        """
        if self.target_pid:
            return psutil.pid_exists(self.target_pid)
        
        # Fallback логика (поиск по имени)
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if (AppConfig.TARGET_PROCESS_NAME in proc.info['name'].lower() and 
                    proc.info['cmdline'] and 
                    AppConfig.TARGET_CMDLINE_KEYWORD in proc.info['cmdline']):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False


# --- VIEW (Графический интерфейс) ---
class VramOverlayView(QWidget):
    """
    View: Отвечает только за отображение данных на экране.
    """
    def __init__(self) -> None:
        super().__init__()
        self._setup_ui()
        self._old_pos: Optional[QPoint] = None

    def _setup_ui(self) -> None:
        """Настройка свойств окна и виджетов."""
        # Флаги окна: без рамок, поверх всех окон, не отображается в панели задач (Tool)
        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput  # Пропускать клики (по умолчанию)
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Метка с текстом
        self.label = QLabel(self)
        self.label.setFont(QFont(AppConfig.FONT_FAMILY, 
                                 AppConfig.FONT_SIZE, 
                                 AppConfig.FONT_WEIGHT))
        
        palette = self.label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor(AppConfig.VRAM_TEXT_COLOR))
        self.label.setPalette(palette)
        
        self.update_text("Init...")

    def update_text(self, text: str) -> None:
        """Обновляет текст метки и подгоняет размер окна."""
        self.label.setText(text)
        self.label.adjustSize()
        self.adjustSize()

    def set_position(self) -> None:
        """Устанавливает начальную позицию (нижний правый угол)."""
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.move(
                geo.width() - self.width() - AppConfig.RIGHT_MARGIN,
                geo.height() - self.height() - AppConfig.BOTTOM_MARGIN
            )

    # --- Обработка перетаскивания (для режима Interactive, если потребуется) ---
    # Для активации перетаскивания нужно убрать флаг WindowTransparentForInput
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._old_pos is not None:
            delta = QPoint(event.globalPosition().toPoint() - self._old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self._old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._old_pos = None


# --- CONTROLLER (Управление логикой) ---
class OverlayController(QObject):
    """
    Controller: Связывает Model и View, управляет таймерами.
    Наследуется от QObject для корректной работы сигналов и слотов.
    """
    def __init__(self, 
                 vram_model: VramMonitorModel, 
                 process_model: ProcessMonitorModel, 
                 view: VramOverlayView) -> None:
        super().__init__()
        self.vram_model = vram_model
        self.process_model = process_model
        self.view = view

        # Таймер обновления VRAM
        self.vram_timer = QTimer(self)
        self.vram_timer.timeout.connect(self._update_vram)
        self.vram_timer.start(AppConfig.POLL_INTERVAL_MS)

        # Таймер проверки процесса
        self.process_timer = QTimer(self)
        self.process_timer.timeout.connect(self._check_process_alive)
        self.process_timer.start(AppConfig.PROCESS_CHECK_INTERVAL_MS)

        # Инициализация
        self.vram_model.initialize()
        self.view.set_position()
        self.view.show()
        
        # Первичное обновление
        self._update_vram()

    @pyqtSlot()
    def _update_vram(self) -> None:
        """Запрашивает данные у модели и передает их в вид."""
        free_mb = self.vram_model.get_free_memory_mb()
        if free_mb is not None:
            self.view.update_text(f"VRAM: {free_mb} MB")
        else:
            self.view.update_text("VRAM: Err")

    @pyqtSlot()
    def _check_process_alive(self) -> None:
        """Проверяет, жив ли ComfyUI. Если нет — закрывает оверлей."""
        if not self.process_model.is_alive():
            logger.info("Родительский процесс не найден. Завершение работы оверлея.")
            QApplication.quit()

    def cleanup(self) -> None:
        """Очистка ресурсов перед выходом."""
        self.vram_timer.stop()
        self.process_timer.stop()
        self.vram_model.shutdown()


# --- ТОЧКА ВХОДА (MAIN) ---
def main() -> None:
    """Запуск приложения."""
    parser = argparse.ArgumentParser(description="MVU VRAM Overlay for ComfyUI")
    parser.add_argument("--pid", type=int, help="PID процесса ComfyUI для мониторинга", default=None)
    args = parser.parse_args()

    app = QApplication(sys.argv)
    
    # Инициализация компонентов MVC
    vram_model = VramMonitorModel()
    process_model = ProcessMonitorModel(target_pid=args.pid)
    view = VramOverlayView()
    
    # Контроллер (теперь корректно наследуется от QObject)
    controller = OverlayController(vram_model, process_model, view)
    
    # Запуск цикла событий
    exit_code = app.exec()
    
    # Завершение
    controller.cleanup()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

"""
MVU VRAM Overlay Node for ComfyUI.

Этот модуль содержит определение пользовательского узла (Custom Node) для ComfyUI,
который управляет жизненным циклом внешнего процесса оверлея VRAM.

Архитектура:
- OverlayProcessManager (Singleton): Управляет subprocess (запуск/остановка).
- MVU_VramOverlay (Node): Интерфейс для ComfyUI.

Author: MVU
License: MIT
"""

import os
import sys
import subprocess
import logging
from typing import Optional, Tuple, Dict, Any

# Настройка логгера для модуля
logger = logging.getLogger("MVU.Nodes")


class OverlayProcessManager:
    """
    Менеджер процесса оверлея (Singleton).
    Отвечает за запуск и остановку внешнего скрипта mvu_overlay_app.py.
    Гарантирует существование только одного экземпляра оверлея.
    """
    _instance: Optional['OverlayProcessManager'] = None
    _process: Optional[subprocess.Popen] = None

    def __new__(cls) -> 'OverlayProcessManager':
        if cls._instance is None:
            cls._instance = super(OverlayProcessManager, cls).__new__(cls)
            logger.debug("OverlayProcessManager initialized.")
        return cls._instance

    @property
    def is_running(self) -> bool:
        """Проверяет, запущен ли процесс и активен ли он."""
        if self._process is None:
            return False
        
        # poll() возвращает None, если процесс еще работает
        if self._process.poll() is None:
            return True
        
        return False

    def start_overlay(self) -> None:
        """Запускает скрипт оверлея как подпроцесс."""
        if self.is_running:
            logger.info("Оверлей уже запущен. Пропуск запуска.")
            return

        current_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(current_dir, "mvu_overlay_app.py")

        if not os.path.exists(script_path):
            logger.error(f"Файл скрипта не найден: {script_path}")
            return

        # Получаем PID текущего процесса (ComfyUI), чтобы передать его оверлею
        current_pid = os.getpid()

        try:
            # Используем тот же интерпретатор Python, который запустил ComfyUI
            cmd = [sys.executable, script_path, "--pid", str(current_pid)]
            
            # Запускаем процесс.
            # subprocess.DETACHED или creationflags могут понадобиться в будущем для скрытия консоли,
            # но для PyQt приложения, запускаемого как скрипт, стандартного Popen достаточно.
            self._process = subprocess.Popen(
                cmd,
                cwd=current_dir,
                # stdout/stderr можно перенаправить в subprocess.PIPE для отладки,
                # но пока оставим None, чтобы видеть вывод в основной консоли ComfyUI (или скрыть его).
            )
            logger.info(f"Оверлей VRAM запущен (PID: {self._process.pid})")
            
        except OSError as e:
            logger.error(f"Не удалось запустить процесс оверлея: {e}")

    def stop_overlay(self) -> None:
        """Останавливает процесс оверлея."""
        if self.is_running and self._process:
            logger.info("Остановка оверлея...")
            self._process.terminate()
            try:
                # Ждем корректного завершения 2 секунды
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logger.warning("Оверлей не ответил на terminate, принудительное завершение (kill).")
                self._process.kill()
            
            self._process = None
            logger.info("Оверлей остановлен.")
        else:
            logger.debug("Попытка остановки неактивного оверлея.")


class MVU_VramOverlay:
    """
    ComfyUI Node: MVU VRAM Overlay
    
    Узел управления отображением использования видеопамяти.
    Позволяет включать и отключать оверлей прямо из workflow.
    """

    def __init__(self) -> None:
        self.manager = OverlayProcessManager()

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        """Определение входных параметров узла."""
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": True, "label": "Enable Overlay"}),
                # mode можно добавить в будущем для переключения стилей
            }
        }

    RETURN_TYPES: Tuple[str] = ("BOOLEAN",)
    RETURN_NAMES: Tuple[str] = ("enabled",)
    FUNCTION = "run"
    OUTPUT_NODE = True  # Указываем, что узел выполняет действие, а не только вычисления
    CATEGORY = "MVU/Utils"

    def run(self, enabled: bool) -> Tuple[bool]:
        """
        Основной метод выполнения узла.
        
        Args:
            enabled (bool): Состояние переключателя во входных параметрах.
            
        Returns:
            Tuple[bool]: Возвращает состояние для дальнейшей передачи (pass-through).
        """
        logger.info(f"MVU VRAM Overlay Node executed. Enabled: {enabled}")

        if enabled:
            self.manager.start_overlay()
        else:
            self.manager.stop_overlay()

        return (enabled,)


# Регистрация классов (хотя в ComfyUI это делается обычно в __init__.py,
# наличие этих словарей здесь полезно для прямой отладки или альтернативных загрузчиков)
NODE_CLASS_MAPPINGS = {
    "MVU_VramOverlay": MVU_VramOverlay
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MVU_VramOverlay": "MVU VRAM Monitor"
}
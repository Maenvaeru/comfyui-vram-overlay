"""
MVU VRAM Overlay Package Initialization.

Этот модуль отвечает за регистрацию пользовательских узлов (Custom Nodes)
в системе ComfyUI. Он экспортирует необходимые словари маппинга,
которые ComfyUI использует для обнаружения и загрузки классов.

Author: MVU
License: MIT
"""

import logging
from typing import Dict, Type, Any

# Импортируем класс ноды из файла nodes.py
from .nodes import MVU_VramOverlay

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
# Настраиваем логгер специально для процесса инициализации пакета
logger = logging.getLogger("MVU.Init")
logger.info("Инициализация пакета MVU VRAM Overlay...")

# --- МАППИНГ КЛАССОВ ---
# Словарь, сопоставляющий внутренние имена нод с их Python-классами.
# Ключ должен быть уникальным во всем пространстве имен ComfyUI.
NODE_CLASS_MAPPINGS: Dict[str, Type[Any]] = {
    "MVU_VramOverlay": MVU_VramOverlay
}

# --- МАППИНГ ОТОБРАЖАЕМЫХ ИМЕН ---
# Словарь, задающий красивые имена для нод в интерфейсе ComfyUI.
# Ключ должен совпадать с ключом в NODE_CLASS_MAPPINGS.
NODE_DISPLAY_NAME_MAPPINGS: Dict[str, str] = {
    "MVU_VramOverlay": "MVU VRAM Monitor"
}

# --- ЭКСПОРТ ---
# Определяем список публичных объектов модуля.
# WEB_DIRECTORY можно добавить, если есть JS-расширения, но здесь они не нужны.
__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS"
]

logger.info(f"Пакет MVU VRAM Overlay успешно загружен. Зарегистрировано узлов: {len(NODE_CLASS_MAPPINGS)}")
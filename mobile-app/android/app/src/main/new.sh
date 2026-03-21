#!/bin/bash

# Пытаемся найти Python 3.14 через лаунчер Windows (py) или напрямую
PYTHON_EXE=$(py -3.14 -c "import sys; print(sys.executable)" 2>/dev/null)

if [ -z "$PYTHON_EXE" ]; then
    echo "Ошибка: Python 3.14 не найден в системе."
    exit 1
fi

echo "Используется Python: $PYTHON_EXE"

# Создаем виртуальное окружение, если его нет
if [ ! -d ".venv" ]; then
    "$PYTHON_EXE" -m venv .venv
fi

# Активация (учитываем Git Bash / MSYS2)
source .venv/Scripts/activate

# Установка зависимостей
python -m pip install --upgrade pip
python -m pip install -q -U google-generativeai

echo "Готово! Gemini CLI зависимости установлены для Python 3.14."

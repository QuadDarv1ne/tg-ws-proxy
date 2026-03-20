@echo off
REM Скрипт для загрузки релиза на GitHub
REM Актуальная версия: 2.10.0
REM Запустите после: gh auth login

set VERSION=v2.10.0

echo Загрузка файлов в релиз %VERSION%...
echo.

REM Проверяем наличие файлов
if not exist "dist\TgWsProxy.exe" (
    echo [ERROR] Файл dist\TgWsProxy.exe не найден!
    echo Выполните сборку: python build_desktop.py windows
    goto :error
)

if not exist "dist\TgWsProxy-Windows.zip" (
    echo [ERROR] Файл dist\TgWsProxy-Windows.zip не найден!
    echo Выполните сборку: python build_desktop.py windows
    goto :error
)

REM Загружаем файлы
echo [1/2] Загрузка TgWsProxy.exe...
gh release upload %VERSION% dist\TgWsProxy.exe --clobber
if %ERRORLEVEL% NEQ 0 goto :error

echo [2/2] Загрузка TgWsProxy-Windows.zip...
gh release upload %VERSION% dist\TgWsProxy-Windows.zip --clobber
if %ERRORLEVEL% NEQ 0 goto :error

echo.
echo ====================================
echo Релиз %VERSION% успешно загружен!
echo ====================================
echo.
echo Ссылка на релиз:
echo https://github.com/Flowseal/tg-ws-proxy/releases/tag/%VERSION%
echo.
goto :end

:error
echo.
echo ====================================
echo Ошибка загрузки!
echo ====================================
echo.
echo Возможные причины:
echo - Вы не аутентифицированы. Выполните: gh auth login
echo - Файлы сборки не найдены в dist\
echo - Нет прав на запись в репозиторий
echo - Релиз %VERSION% не создан. Создайте: gh release create %VERSION%
echo.

:end
pause

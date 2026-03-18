@echo off
REM Скрипт для загрузки релиза v1.3.0 на GitHub
REM Запустите после: gh auth login

echo Загрузка TgWsProxy.exe в релиз v1.3.0...
gh release upload v1.3.0 dist\TgWsProxy.exe --clobber

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ====================================
    echo Релиз v1.3.0 успешно загружен!
    echo ====================================
    echo.
    echo Ссылка на релиз:
    echo https://github.com/QuadDarv1ne/tg-ws-proxy/releases/tag/v1.3.0
) else (
    echo.
    echo ====================================
    echo Ошибка загрузки!
    echo ====================================
    echo.
    echo Возможные причины:
    echo - Вы не аутентифицированы. Выполните: gh auth login
    echo - Файл dist\TgWsProxy.exe не найден
    echo - Нет прав на запись в репозиторий
)

pause

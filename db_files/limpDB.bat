@echo off
:: Define o nome da aplicação, conforme definido na função get_app_data_dir do código Python.
set "APP_NAME=processSimul"

:: Concatena o caminho da pasta de dados da aplicação (no Windows, normalmente %APPDATA%\processSimul)
set "APPDATA_DIR=%APPDATA%\%APP_NAME%"

echo Tentando apagar a pasta: "%APPDATA_DIR%"

:: Verifica se a pasta existe e a apaga junto com todos os seus conteúdos de forma recursiva (/s) e silenciosa (/q)
if exist "%APPDATA_DIR%" (
    rd /s /q "%APPDATA_DIR%"
    echo Pasta apagada com sucesso.
) else (
    echo A pasta nao foi encontrada.
)

pause
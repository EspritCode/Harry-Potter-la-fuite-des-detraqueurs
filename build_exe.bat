@echo off
REM ===================================================================
REM  Construit HarryPotter.exe a partir de harry_potter.py
REM  Double-cliquez sur ce fichier, ou lancez-le depuis un terminal.
REM ===================================================================

setlocal
cd /d "%~dp0"

echo.
echo === Verification de Python ===
where python >nul 2>nul
if errorlevel 1 (
    echo ERREUR : Python n'est pas installe, ou pas dans le PATH.
    echo Installez-le depuis https://www.python.org/downloads/ en cochant
    echo "Add python.exe to PATH", puis relancez ce script.
    pause
    exit /b 1
)
python --version

echo.
echo === Installation des dependances ===
python -m pip install --upgrade pip
python -m pip install "pygame>=2.6" "pyinstaller>=6.0"
if errorlevel 1 (
    echo ERREUR : installation des dependances impossible.
    pause
    exit /b 1
)

echo.
echo === Generation de l'icone ===
python make_icon.py
if errorlevel 1 echo (icone non generee, l'executable aura l'icone par defaut)

echo.
echo === Verification du jeu ===
python -c "import pygame, harry_potter" 2>nul
if errorlevel 1 (
    echo Le module ne s'importe pas seul, on continue quand meme :
    echo les erreurs eventuelles seront visibles dans crash.log au lancement.
)

echo.
echo === Compilation de l'executable ===
python -m PyInstaller --noconfirm --clean harry_potter.spec
if errorlevel 1 (
    echo.
    echo ERREUR : la compilation a echoue. Lisez les messages ci-dessus.
    pause
    exit /b 1
)

echo.
echo ===================================================================
echo  Termine : dist\HarryPotter.exe
echo ===================================================================
if exist "dist\HarryPotter.exe" (
    echo L'executable a bien ete cree.
) else (
    echo ATTENTION : dist\HarryPotter.exe est introuvable.
)
echo.
pause

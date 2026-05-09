@echo off
setlocal

set /p COMMIT_MESSAGE=Commit message: 
if "%COMMIT_MESSAGE%"=="" (
  echo Commit message is required.
  exit /b 1
)

git add .
if errorlevel 1 exit /b %errorlevel%

git commit -m "%COMMIT_MESSAGE%"
if errorlevel 1 exit /b %errorlevel%

git push
if errorlevel 1 exit /b %errorlevel%

echo Dashboard update pushed.

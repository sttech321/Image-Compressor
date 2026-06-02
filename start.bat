@echo off
REM Start Image Compressor App (Backend + Frontend)

echo ============================================
echo Image Compressor - Startup Script
echo ============================================
echo.
echo Starting Backend (Flask)...
echo.

REM Start backend in a new window
start cmd /k "cd backend && python app.py"

timeout /t 3 /nobreak

echo Starting Frontend (Next.js)...
echo.

REM Start frontend in another new window
start cmd /k "cd frontend && npm run dev"

echo.
echo ============================================
echo Backend running on: http://localhost:5000
echo Frontend running on: http://localhost:3000
echo ============================================
echo.
echo Open http://localhost:3000 in your browser
echo.

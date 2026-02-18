# DGSpace - Start both servers
# Run this script whenever you want to start the project

$venv = "E:\DGSpace-Project-1\.venv\Scripts\python.exe"
$backend = "E:\DGSpace-Project-1\backend\app.py"
$frontend = "E:\DGSpace-Project-1\frontend\manage.py"

Write-Host "Starting Flask backend on port 5000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd E:\DGSpace-Project-1\backend; & '$venv' '$backend'"

Write-Host "Starting Django frontend on port 8000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd E:\DGSpace-Project-1\frontend; & '$venv' '$frontend' runserver 8000"

Write-Host ""
Write-Host "Both servers are starting in separate windows." -ForegroundColor Green
Write-Host "Open your browser and go to: http://localhost:8000" -ForegroundColor Green
Write-Host ""
Write-Host "Verification codes will appear in the Flask window." -ForegroundColor Yellow

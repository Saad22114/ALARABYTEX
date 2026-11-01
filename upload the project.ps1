
cd "D:\QOMASH\site working\site 3 open code"

git add .
git commit -m "Update latest project changes"

git pull --rebase origin main

if ($LASTEXITCODE -eq 0) {
    git push origin main
} else {
    Write-Host "Rebase failed. Resolve conflicts before pushing." -ForegroundColor Red
}

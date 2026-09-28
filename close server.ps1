foreach ($port in 8001, 9012) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue

    foreach ($connection in $connections) {
        Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Backend (8001) and Frontend (9012) stopped." -ForegroundColor Green
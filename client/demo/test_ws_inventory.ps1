# 端到端测试库存 WS 实时推送
# 流程：admin 登录 -> 开 WS 监听 -> 增/改/删 inventory -> 收事件 -> 断开

$ErrorActionPreference = 'Stop'

# 1. admin 登录拿 token
$login = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/admin/auth/login' `
    -Method POST -ContentType 'application/json' `
    -Body (@{ username = 'admin'; password = 'admin123' } | ConvertTo-Json)
$token = $login.token
Write-Host "[OK] admin login | token=$($token.Substring(0,20))..." -ForegroundColor Green

# 2. 起 WS 监听（异步任务）
$wsJob = Start-Job -ScriptBlock {
    param($token)
    Add-Type -AssemblyName 'System.Net.WebSockets'
    $ws = [System.Net.WebSockets.ClientWebSocket]::new()
    $url = "ws://127.0.0.1:8000/api/v1/admin/ws/inventory?token=$token"
    $cts = [System.Threading.CancellationTokenSource]::new()
    $ws.ConnectAsync([Uri]$url, $cts.Token).Wait()
    Write-Output "[WS] connected"
    $buf = [System.Net.WebSockets.WebSocket]::CreateClientBuffer(8192, 8192)
    $events = @()
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt 30) {
        $task = $ws.ReceiveAsync($buf, $cts.Token)
        if (-not $task.Wait(2000)) { continue }
        $r = $task.Result
        if ($r.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) { break }
        $text = [System.Text.Encoding]::UTF8.GetString($buf.Array, 0, $r.Count)
        Write-Output "[WS] recv: $text"
        $events += $text
        if ($events.Count -ge 4) { break }   # ready + create + update + delete
    }
    try { $ws.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, '', $cts.Token).Wait(2000) } catch {}
    return $events
} -ArgumentList $token

Start-Sleep -Seconds 1
Write-Host "[OK] WS job started" -ForegroundColor Green

# 3. 创建 inventory
$inv = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/admin/inventory' `
    -Method POST -ContentType 'application/json' `
    -Headers @{ Authorization = "Bearer $token" } `
    -Body (@{
        device_id = 'ws-test-device'
        category = 'WS测试食材'
        status = 'IN_STOCK'
        remain_ratio = 1.0
        agent_metadata = @{ confidence = 0.95 }
    } | ConvertTo-Json)
$invId = $inv.id
Write-Host "[OK] created inventory | id=$invId" -ForegroundColor Green

Start-Sleep -Seconds 1

# 4. 更新 inventory
$null = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/admin/inventory/$invId" `
    -Method PUT -ContentType 'application/json' `
    -Headers @{ Authorization = "Bearer $token" } `
    -Body (@{ remain_ratio = 0.5; status = 'OUT_PENDING' } | ConvertTo-Json)
Write-Host "[OK] updated inventory" -ForegroundColor Green

Start-Sleep -Seconds 1

# 5. 删除 inventory
$null = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/admin/inventory/$invId" `
    -Method DELETE -Headers @{ Authorization = "Bearer $token" }
Write-Host "[OK] deleted inventory" -ForegroundColor Green

# 6. 收齐 WS 事件
Start-Sleep -Seconds 2
$events = Receive-Job -Job $wsJob -Wait
Remove-Job -Job $wsJob -Force

Write-Host "`n========== WS Events =========="
$events | ForEach-Object { Write-Host $_ -ForegroundColor Cyan }
Write-Host "================================"

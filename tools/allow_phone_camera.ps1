param(
    [Parameter(Mandatory=$true)][string]$HostAddress,
    [Parameter(Mandatory=$true)][string]$Ports,
    [Parameter(Mandatory=$true)][ValidateRange(1,2147483647)][int]$AppPid
)
$ErrorActionPreference = 'Stop'
try {
    $cameraIp = [System.Net.IPAddress]::Parse($HostAddress)
    if ($cameraIp.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { throw '需要局域网 IPv4 地址。' }
    $cameraBytes = $cameraIp.GetAddressBytes()
    if (-not ($cameraBytes[0] -eq 10 -or ($cameraBytes[0] -eq 172 -and $cameraBytes[1] -ge 16 -and $cameraBytes[1] -le 31) -or ($cameraBytes[0] -eq 192 -and $cameraBytes[1] -eq 168))) { throw '只允许局域网地址。' }
    if ($Ports -notmatch '^\d{1,5},\d{1,5}$') { throw '端口参数无效。' }
    $cameraPorts = @($Ports.Split(',') | ForEach-Object { [int]$_ } | Select-Object -Unique)
    if ($cameraPorts.Count -ne 2 -or @($cameraPorts | Where-Object { $_ -lt 1 -or $_ -gt 65535 }).Count) { throw '端口范围无效。' }
    $cameraProcess = Get-Process -Id $AppPid
    $cameraProgram = $cameraProcess.Path
    if (-not $cameraProgram) { throw '无法确定摄像头服务的程序路径。' }
    $cameraListeners = @(Get-NetTCPConnection -State Listen -OwningProcess $AppPid | Where-Object { $_.LocalAddress -eq $HostAddress })
    foreach ($cameraPort in $cameraPorts) {
        if (-not @($cameraListeners | Where-Object { $_.LocalPort -eq $cameraPort }).Count) { throw '本次连接已经关闭，请重新生成二维码。' }
    }
    $cameraFilters = @(Get-NetFirewallApplicationFilter | Where-Object {
        [System.Environment]::ExpandEnvironmentVariables($_.Program).Trim('"') -eq $cameraProgram
    })
    $cameraBlocks = @($cameraFilters | Get-NetFirewallRule | Where-Object {
        $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Block'
    })
    # Do not override an all-profile policy or change the network's category.
    if (@($cameraBlocks | Where-Object { $_.Profile.ToString() -eq 'Any' -or ($_.Profile.ToString() -ne 'Public' -and $_.Profile.ToString() -match 'Public') }).Count) {
        throw '此程序有覆盖所有网络的阻止规则，请在 Windows 安全中心手动检查；没有修改规则。'
    }
    # Windows creates explicit Public-only blocks when its first Python access
    # prompt is declined. Those blocks override narrower allow rules.
    $cameraPublicBlocks = @($cameraBlocks | Where-Object { $_.Profile.ToString() -eq 'Public' })
    $cameraAdded = @()
    try {
        foreach ($cameraPort in $cameraPorts) {
            $cameraRuleName = "FlowTodoPhoneCamera-$AppPid-$cameraPort"
            if (-not (Get-NetFirewallRule -Name $cameraRuleName -ErrorAction SilentlyContinue)) {
                New-NetFirewallRule -Name $cameraRuleName -DisplayName "FlowTodo 手机镜头 ($cameraPort)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $cameraPort -LocalAddress $HostAddress -RemoteAddress LocalSubnet -Program $cameraProgram -Profile Any | Out-Null
                $cameraAdded += $cameraRuleName
            }
        }
        foreach ($cameraBlock in $cameraPublicBlocks) { $cameraBlock | Disable-NetFirewallRule | Out-Null }
    } catch {
        foreach ($cameraRuleName in $cameraAdded) { Remove-NetFirewallRule -Name $cameraRuleName -ErrorAction SilentlyContinue }
        foreach ($cameraBlock in $cameraPublicBlocks) { $cameraBlock | Enable-NetFirewallRule -ErrorAction SilentlyContinue | Out-Null }
        throw
    }
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'FlowTodo 局域网连接修复') | Out-Null
    exit 1
}

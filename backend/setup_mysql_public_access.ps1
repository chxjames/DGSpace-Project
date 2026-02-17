# MySQL 公网访问和 Aiven 迁移配置脚本
# 警告：此操作有安全风险，请确保你了解后果
# 基于 Aiven 官方文档要求

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MySQL Aiven 迁移完整配置向导" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "⚠️  警告：开放 MySQL 到公网有安全风险！" -ForegroundColor Red
Write-Host "建议：只在测试环境使用，生产环境请使用云数据库" -ForegroundColor Yellow
Write-Host ""
Write-Host "此脚本将配置：" -ForegroundColor Yellow
Write-Host "1. bind-address = 0.0.0.0 (允许远程连接)" -ForegroundColor White
Write-Host "2. GTID 模式 (事务唯一标识)" -ForegroundColor White
Write-Host "3. 逻辑复制权限" -ForegroundColor White
Write-Host "4. Windows 防火墙规则" -ForegroundColor White
Write-Host ""

$confirm = Read-Host "确定要继续吗？(输入 YES 继续)"
if ($confirm -ne "YES") {
    Write-Host "操作已取消" -ForegroundColor Yellow
    exit
}

Write-Host ""
Write-Host "步骤 1: 备份 MySQL 配置文件..." -ForegroundColor Green

$configPath = "C:\ProgramData\MySQL\MySQL Server 8.0\my.ini"
$backupPath = "C:\ProgramData\MySQL\MySQL Server 8.0\my.ini.backup"

try {
    Copy-Item $configPath $backupPath -Force
    Write-Host "✅ 配置文件已备份到: $backupPath" -ForegroundColor Green
} catch {
    Write-Host "❌ 备份失败: $_" -ForegroundColor Red
    exit
}

Write-Host ""
Write-Host "步骤 2: 修改 MySQL 配置文件..." -ForegroundColor Green
Write-Host "  - 设置 bind-address = 0.0.0.0" -ForegroundColor White
Write-Host "  - 启用 GTID 模式" -ForegroundColor White
Write-Host "  - 启用 GTID 一致性" -ForegroundColor White

try {
    $content = Get-Content $configPath
    $newContent = @()
    $inMysqldSection = $false
    $hasBindAddress = $false
    $hasGtidMode = $false
    $hasEnforceGtid = $false
    
    foreach ($line in $content) {
        # 检测 [mysqld] 部分
        if ($line -match '^\[mysqld\]') {
            $inMysqldSection = $true
            $newContent += $line
            continue
        }
        
        # 检测其他部分开始
        if ($line -match '^\[.+\]' -and $line -notmatch '^\[mysqld\]') {
            $inMysqldSection = $false
        }
        
        # 在 mysqld 部分修改或添加配置
        if ($inMysqldSection) {
            # 修改 bind-address
            if ($line -match '^bind-address') {
                $newContent += "bind-address = 0.0.0.0"
                $hasBindAddress = $true
                continue
            }
            
            # 修改 gtid_mode
            if ($line -match '^gtid_mode') {
                $newContent += "gtid_mode = ON"
                $hasGtidMode = $true
                continue
            }
            
            # 修改 enforce_gtid_consistency
            if ($line -match '^enforce_gtid_consistency') {
                $newContent += "enforce_gtid_consistency = ON"
                $hasEnforceGtid = $true
                continue
            }
        }
        
        $newContent += $line
    }
    
    # 如果缺少配置，添加到 [mysqld] 部分
    if (!$hasBindAddress -or !$hasGtidMode -or !$hasEnforceGtid) {
        $finalContent = @()
        foreach ($line in $newContent) {
            $finalContent += $line
            if ($line -match '^\[mysqld\]') {
                if (!$hasBindAddress) {
                    $finalContent += "bind-address = 0.0.0.0"
                }
                if (!$hasGtidMode) {
                    $finalContent += "gtid_mode = ON"
                }
                if (!$hasEnforceGtid) {
                    $finalContent += "enforce_gtid_consistency = ON"
                }
            }
        }
        $newContent = $finalContent
    }
    
    Set-Content $configPath $newContent -Force
    Write-Host "✅ 配置文件已更新：" -ForegroundColor Green
    Write-Host "   - bind-address = 0.0.0.0" -ForegroundColor Cyan
    Write-Host "   - gtid_mode = ON" -ForegroundColor Cyan
    Write-Host "   - enforce_gtid_consistency = ON" -ForegroundColor Cyan
} catch {
    Write-Host "❌ 修改配置文件失败: $_" -ForegroundColor Red
    Write-Host "请以管理员身份运行此脚本" -ForegroundColor Yellow
    exit
}

Write-Host ""
Write-Host "步骤 3: 配置 Windows 防火墙..." -ForegroundColor Green

try {
    $ruleName = "MySQL Server 3306"
    
    # 检查规则是否存在
    $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    
    if ($existingRule) {
        Write-Host "防火墙规则已存在，更新中..." -ForegroundColor Yellow
        Set-NetFirewallRule -DisplayName $ruleName -Enabled True
    } else {
        New-NetFirewallRule -DisplayName $ruleName `
            -Direction Inbound `
            -Protocol TCP `
            -LocalPort 3306 `
            -Action Allow `
            -Profile Any
    }
    
    Write-Host "✅ Windows 防火墙已开放 3306 端口" -ForegroundColor Green
} catch {
    Write-Host "❌ 防火墙配置失败: $_" -ForegroundColor Red
    Write-Host "请手动在 Windows 防火墙中开放 3306 端口" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "步骤 4: 重启 MySQL 服务..." -ForegroundColor Green

try {
    Restart-Service MySQL80
    Start-Sleep -Seconds 3
    
    $service = Get-Service MySQL80
    if ($service.Status -eq "Running") {
        Write-Host "✅ MySQL 服务已重启" -ForegroundColor Green
    } else {
        Write-Host "❌ MySQL 服务启动失败" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ 重启服务失败: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "步骤 5: 创建远程访问用户..." -ForegroundColor Green

$mysqlPassword = Read-Host "输入 MySQL root 密码" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($mysqlPassword)
$password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

$sql = @"
CREATE USER IF NOT EXISTS 'aiven_migration'@'%' IDENTIFIED BY 'AivenMigration2026!';
GRANT ALL PRIVILEGES ON dgspace.* TO 'aiven_migration'@'%';
FLUSH PRIVILEGES;
"@

$sql | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p$password 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 远程用户已创建" -ForegroundColor Green
    Write-Host "   用户名: aiven_migration" -ForegroundColor Cyan
    Write-Host "   密码: AivenMigration2026!" -ForegroundColor Cyan
} else {
    Write-Host "❌ 创建用户失败" -ForegroundColor Red
}

Write-Host ""
Write-Host "步骤 6: 获取公网 IP 地址..." -ForegroundColor Green

try {
    $publicIP = (Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing).Content
    Write-Host "✅ 你的公网 IP 地址: $publicIP" -ForegroundColor Green
} catch {
    Write-Host "❌ 无法获取公网 IP" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "配置完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "接下来你需要：" -ForegroundColor Yellow
Write-Host "1. 在路由器中配置端口转发：" -ForegroundColor White
Write-Host "   外部端口: 3306 -> 内部 IP: [你的电脑局域网IP] -> 内部端口: 3306"
Write-Host ""
Write-Host "2. 在 Aiven 迁移工具中使用：" -ForegroundColor White
Write-Host "   Hostname: $publicIP (你的公网IP)" -ForegroundColor Cyan
Write-Host "   Port: 3306" -ForegroundColor Cyan
Write-Host "   Username: aiven_migration" -ForegroundColor Cyan
Write-Host "   Password: AivenMigration2026!" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️  重要提醒：" -ForegroundColor Red
Write-Host "- 完成迁移后请立即关闭端口转发" -ForegroundColor Yellow
Write-Host "- 删除远程用户以提高安全性" -ForegroundColor Yellow
Write-Host "- 恢复 bind-address = 127.0.0.1" -ForegroundColor Yellow
Write-Host ""

# 显示本机局域网 IP
Write-Host "你的局域网 IP 地址（配置路由器时需要）：" -ForegroundColor Cyan
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne "127.0.0.1"} | Select-Object IPAddress, InterfaceAlias

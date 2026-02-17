"""检查 MySQL 公网访问配置状态"""
import subprocess
import socket

print("=" * 70)
print("🔍 MySQL 公网访问配置检查")
print("=" * 70)
print()

# 1. 检查 MySQL 服务状态
print("1️⃣ 检查 MySQL 服务...")
try:
    result = subprocess.run(['sc', 'query', 'MySQL80'], capture_output=True, text=True)
    if 'RUNNING' in result.stdout:
        print("   ✅ MySQL 服务正在运行")
    else:
        print("   ❌ MySQL 服务未运行")
except Exception as e:
    print(f"   ❌ 无法检查服务: {e}")

print()

# 2. 检查 MySQL 是否监听 0.0.0.0
print("2️⃣ 检查 MySQL 监听地址...")
try:
    result = subprocess.run(['netstat', '-an'], capture_output=True, text=True)
    if '0.0.0.0:3306' in result.stdout or '*:3306' in result.stdout:
        print("   ✅ MySQL 正在监听 0.0.0.0:3306 (允许外部连接)")
    elif '127.0.0.1:3306' in result.stdout:
        print("   ❌ MySQL 仅监听 127.0.0.1:3306 (仅本地)")
        print("   需要修改 my.ini 中的 bind-address")
    else:
        print("   ⚠️  未找到 3306 端口监听")
except Exception as e:
    print(f"   ❌ 无法检查端口: {e}")

print()

# 3. 检查防火墙规则
print("3️⃣ 检查 Windows 防火墙...")
try:
    result = subprocess.run(
        ['powershell', '-Command', 'Get-NetFirewallRule -DisplayName "MySQL Server 3306" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Enabled'],
        capture_output=True, text=True
    )
    if 'True' in result.stdout:
        print("   ✅ 防火墙规则已启用")
    else:
        print("   ❌ 防火墙规则未启用或不存在")
except Exception as e:
    print(f"   ⚠️  无法检查防火墙: {e}")

print()

# 4. 检查配置文件
print("4️⃣ 检查 my.ini 配置...")
try:
    with open(r"C:\ProgramData\MySQL\MySQL Server 8.0\my.ini", 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        if 'bind-address' in content:
            import re
            match = re.search(r'bind-address\s*=\s*(\S+)', content)
            if match:
                bind_addr = match.group(1)
                if bind_addr in ['0.0.0.0', '*']:
                    print(f"   ✅ bind-address = {bind_addr} (允许外部连接)")
                else:
                    print(f"   ❌ bind-address = {bind_addr} (仅本地)")
        else:
            print("   ⚠️  未找到 bind-address 配置")
            
        # 检查备份文件
        import os
        if os.path.exists(r"C:\ProgramData\MySQL\MySQL Server 8.0\my.ini.backup"):
            print("   ✅ 配置文件备份存在")
        else:
            print("   ⚠️  未找到配置文件备份")
except Exception as e:
    print(f"   ❌ 无法读取配置文件: {e}")

print()

# 5. 获取公网 IP
print("5️⃣ 获取公网 IP 地址...")
try:
    import urllib.request
    with urllib.request.urlopen('https://api.ipify.org') as response:
        public_ip = response.read().decode('utf-8')
        print(f"   ✅ 公网 IP: {public_ip}")
except Exception as e:
    print(f"   ❌ 无法获取公网 IP: {e}")

print()

# 6. 获取局域网 IP
print("6️⃣ 获取局域网 IP...")
try:
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"   ✅ 局域网 IP: {local_ip}")
    print(f"   (路由器端口转发需要使用此 IP)")
except Exception as e:
    print(f"   ❌ 无法获取局域网 IP: {e}")

print()
print("=" * 70)
print("📋 总结")
print("=" * 70)
print()
print("如果所有检查都通过，还需要：")
print("1. ✅ 在路由器中配置端口转发:")
print("   外部端口: 3306 -> 内部 IP: [局域网IP] -> 内部端口: 3306")
print()
print("2. ✅ 在 Aiven 迁移工具中使用:")
print("   Hostname: [公网IP]")
print("   Port: 3306")
print("   Username: aiven_migration (或 root)")
print("   Password: AivenMigration2026! (或 X@ch20030610)")
print()
print("⚠️  迁移完成后，记得恢复安全配置！")
print("=" * 70)

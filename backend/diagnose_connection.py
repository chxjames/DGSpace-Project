"""测试 MySQL 公网连接性"""
import socket
import subprocess

print("=" * 70)
print("🔍 MySQL 公网连接诊断")
print("=" * 70)
print()

# 1. 测试本地连接
print("1️⃣ 测试本地连接 (localhost:3306)...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex(('127.0.0.1', 3306))
    sock.close()
    
    if result == 0:
        print("   ✅ 本地连接成功")
    else:
        print(f"   ❌ 本地连接失败 (错误代码: {result})")
except Exception as e:
    print(f"   ❌ 测试失败: {e}")

print()

# 2. 测试局域网连接
print("2️⃣ 测试局域网连接 (192.168.56.1:3306)...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex(('192.168.56.1', 3306))
    sock.close()
    
    if result == 0:
        print("   ✅ 局域网连接成功")
    else:
        print(f"   ❌ 局域网连接失败 (错误代码: {result})")
except Exception as e:
    print(f"   ❌ 测试失败: {e}")

print()

# 3. 检查防火墙规则详情
print("3️⃣ 检查防火墙规则详情...")
try:
    result = subprocess.run(
        ['powershell', '-Command', 
         'Get-NetFirewallRule -DisplayName "MySQL Server 3306" | Get-NetFirewallPortFilter | Select-Object LocalPort, Protocol'],
        capture_output=True, text=True
    )
    if result.stdout:
        print(f"   {result.stdout.strip()}")
        print("   ✅ 防火墙规则详情如上")
    else:
        print("   ❌ 无法获取防火墙规则详情")
except Exception as e:
    print(f"   ⚠️  {e}")

print()

# 4. 检查是否在路由器后面
print("4️⃣ 检查网络环境...")
print("   你的公网 IP: 208.71.27.69")
print("   你的局域网 IP: 192.168.56.1")
print()
if "192.168" in "192.168.56.1" or "10." in "192.168.56.1" or "172." in "192.168.56.1":
    print("   ⚠️  你在路由器/NAT后面（局域网IP是私有地址）")
    print("   需要在路由器配置端口转发才能从外网访问")
else:
    print("   ✅ 你有公网 IP，不需要端口转发")

print()
print("=" * 70)
print("📋 诊断结果")
print("=" * 70)
print()
print("❌ Aiven 无法连接的原因：")
print()
print("【最可能】路由器未配置端口转发")
print("   解决方法：")
print("   1. 登录路由器管理界面")
print("   2. 找到 '端口转发' / '虚拟服务器' / 'Port Forwarding'")
print("   3. 添加规则：")
print("      - 服务名称: MySQL")
print("      - 外部端口: 3306")
print("      - 内部 IP: 192.168.56.1")
print("      - 内部端口: 3306")
print("      - 协议: TCP")
print("   4. 保存并重启路由器（如果需要）")
print()
print("【其他可能】ISP 封锁了 3306 端口")
print("   某些运营商会封锁常见端口")
print("   解决方法：使用非标准端口（如 13306）")
print()
print("【检查方法】在外网测试")
print("   1. 用手机（关闭 WiFi，使用移动数据）")
print("   2. 或从其他网络（朋友家、咖啡店）")
print("   3. 运行: telnet 208.71.27.69 3306")
print("   4. 或使用在线工具: https://www.yougetsignal.com/tools/open-ports/")
print()
print("=" * 70)
print()
print("💡 推荐方案（最简单、最安全）：")
print("   不要开放本地数据库到公网")
print("   继续使用云数据库（已经成功同步）")
print("   运行: python sync_local_to_cloud.py")
print("   当有更新时再同步一次即可")
print("=" * 70)

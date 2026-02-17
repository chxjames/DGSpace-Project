# DGSpace API 测试指南

## 🚀 无需前端即可测试后端 API

### 方法 1: 使用 PowerShell / curl

#### 1. 学生注册
```powershell
$body = @{
    email = "test@sandiego.edu"
    password = "Test123!"
    full_name = "Test Student"
    department = "Computer Science"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/api/students/register" -Method POST -Body $body -ContentType "application/json"
```

#### 2. 验证邮箱
```powershell
$body = @{
    email = "test@sandiego.edu"
    verification_code = "123456"  # 从数据库或邮件中获取
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/api/students/verify-email" -Method POST -Body $body -ContentType "application/json"
```

#### 3. 学生登录
```powershell
$body = @{
    email = "test@sandiego.edu"
    password = "Test123!"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:5000/api/students/login" -Method POST -Body $body -ContentType "application/json"
$token = $response.token
Write-Host "Token: $token"
```

#### 4. 管理员登录
```powershell
$body = @{
    email = "chenghaoxu@sandiego.edu"
    password = "Admin123!"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/api/admins/login" -Method POST -Body $body -ContentType "application/json"
```

#### 5. 获取用户信息（需要 token）
```powershell
$headers = @{
    "Authorization" = "Bearer $token"
}

Invoke-RestMethod -Uri "http://localhost:5000/api/profile" -Method GET -Headers $headers
```

---

### 方法 2: 使用 Python 测试脚本

创建一个测试脚本来验证所有 API：

```python
import requests
import json

BASE_URL = "http://localhost:5000"

# 1. 测试学生注册
print("测试学生注册...")
response = requests.post(f"{BASE_URL}/api/students/register", json={
    "email": "test@sandiego.edu",
    "password": "Test123!",
    "full_name": "Test Student",
    "department": "Computer Science"
})
print(f"状态码: {response.status_code}")
print(f"响应: {response.json()}")

# 2. 测试管理员登录
print("\n测试管理员登录...")
response = requests.post(f"{BASE_URL}/api/admins/login", json={
    "email": "chenghaoxu@sandiego.edu",
    "password": "Admin123!"
})
print(f"状态码: {response.status_code}")
print(f"响应: {response.json()}")

if response.status_code == 200:
    token = response.json()['token']
    print(f"Token: {token}")
    
    # 3. 测试获取用户信息
    print("\n测试获取用户信息...")
    response = requests.get(f"{BASE_URL}/api/profile", 
                          headers={"Authorization": f"Bearer {token}"})
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
```

---

### 方法 3: 使用 Postman（推荐）

1. 下载 Postman: https://www.postman.com/downloads/
2. 创建新的 Collection: "DGSpace API"
3. 添加请求测试所有端点

---

### 方法 4: 创建简单的 HTML 测试页面

快速创建一个测试前端：

```html
<!DOCTYPE html>
<html>
<head>
    <title>DGSpace API 测试</title>
</head>
<body>
    <h1>学生注册测试</h1>
    <button onclick="testRegister()">测试注册</button>
    <button onclick="testLogin()">测试登录</button>
    <pre id="result"></pre>

    <script>
        const API_URL = 'http://localhost:5000';
        
        async function testRegister() {
            const response = await fetch(`${API_URL}/api/students/register`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    email: 'test@sandiego.edu',
                    password: 'Test123!',
                    full_name: 'Test Student',
                    department: 'Computer Science'
                })
            });
            const data = await response.json();
            document.getElementById('result').textContent = JSON.stringify(data, null, 2);
        }
        
        async function testLogin() {
            const response = await fetch(`${API_URL}/api/admins/login`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    email: 'chenghaoxu@sandiego.edu',
                    password: 'Admin123!'
                })
            });
            const data = await response.json();
            document.getElementById('result').textContent = JSON.stringify(data, null, 2);
        }
    </script>
</body>
</html>
```

---

## 🎯 推荐工作流程：

1. **现在**: 用 Postman/Python 测试所有 API 端点
2. **同时**: 继续开发新的后端功能
3. **前端完成后**: 对接前端，修复集成问题

---

## 📋 你可以继续开发的功能：

- ✅ 添加更多 API 端点（3D打印请求管理）
- ✅ 完善权限控制
- ✅ 添加数据验证
- ✅ 实现文件上传（3D模型）
- ✅ 添加搜索/过滤功能
- ✅ 实现通知系统
- ✅ 优化数据库查询
- ✅ 编写单元测试

**后端和前端可以并行开发！** 🚀

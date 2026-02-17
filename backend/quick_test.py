"""快速测试 DGSpace 后端 API"""
import requests
import json

BASE_URL = "http://localhost:5000"

def print_response(title, response):
    """打印格式化的响应"""
    print("\n" + "=" * 70)
    print(f"🧪 {title}")
    print("=" * 70)
    print(f"状态码: {response.status_code}")
    try:
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except:
        print(f"响应: {response.text}")
    print("=" * 70)

def test_api():
    """测试所有主要 API 端点"""
    
    print("\n🚀 开始测试 DGSpace 后端 API")
    print("确保 Flask 服务器正在运行: http://localhost:5000\n")
    
    # 测试连接
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"✅ 服务器连接成功")
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        print("请先运行: cd E:\\DGSpace-Project\\backend && python app.py")
        return
    
    # 1. 测试管理员登录（使用现有管理员）
    print_response(
        "测试 1: 管理员登录",
        requests.post(f"{BASE_URL}/api/admins/login", json={
            "email": "chenghaoxu@sandiego.edu",
            "password": "Admin123!"  # 你需要知道正确的密码
        })
    )
    
    # 2. 测试学生注册
    print_response(
        "测试 2: 学生注册",
        requests.post(f"{BASE_URL}/api/students/register", json={
            "email": f"test{hash('test') % 10000}@sandiego.edu",  # 随机邮箱
            "password": "Test123!",
            "full_name": "Test Student",
            "department": "Computer Science"
        })
    )
    
    # 3. 查看数据库当前状态
    print("\n" + "=" * 70)
    print("📊 查看云数据库当前数据")
    print("=" * 70)
    
    try:
        from config import Config
        import mysql.connector
        
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            ssl_disabled=False
        )
        
        cursor = conn.cursor()
        
        # 统计学生数
        cursor.execute("SELECT COUNT(*) FROM students")
        student_count = cursor.fetchone()[0]
        print(f"学生总数: {student_count}")
        
        # 统计管理员数
        cursor.execute("SELECT COUNT(*) FROM admins")
        admin_count = cursor.fetchone()[0]
        print(f"管理员总数: {admin_count}")
        
        # 统计待验证邮箱
        cursor.execute("SELECT COUNT(*) FROM email_verification_codes")
        pending_count = cursor.fetchone()[0]
        print(f"待验证邮箱: {pending_count}")
        
        conn.close()
        print("=" * 70)
        
    except Exception as e:
        print(f"无法连接数据库: {e}")
    
    print("\n✅ API 测试完成！")
    print("\n💡 提示:")
    print("- 你可以用 Postman 进行更详细的测试")
    print("- 前端团队可以使用这些 API 端点")
    print("- API 文档在: backend/README.md")

if __name__ == "__main__":
    test_api()

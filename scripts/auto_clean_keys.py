#!/usr/bin/env python3
"""
自动清理无效API密钥脚本
"""

import json
import sqlite3
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def clean_keys():
    """基于测试结果清理密钥"""
    db_path = "data/gemini_balance.db"

    # 根据刚才的测试结果，这些是有效的密钥数量
    # 我们将直接更新数据库，移除被暂停的密钥

    print("🧹 开始清理无效的API密钥...")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 获取当前API密钥
        cursor.execute("SELECT value FROM t_settings WHERE key = 'API_KEYS'")
        result = cursor.fetchone()

        if not result or not result[0]:
            print("❌ 没有找到API密钥")
            return

        api_keys = json.loads(result[0])
        print(f"📊 当前有 {len(api_keys)} 个API密钥")

        # 被暂停的密钥列表（从测试结果中提取）
        suspended_keys = [
            "AIzaSyCFRo1wCj7Muph5IwD0BqU4v77zWWgt8Lc",
            "AIzaSyAxUd9NCOeDV1JOuE5sc2lLApWfT24ylqA",
            "AIzaSyDPrv1RxoMt0pDqAyiD_YKL2dgzm6nKJLA",
            "AIzaSyAbOYG3PL7qpCBJ_p7MQF3LQB2ThE",
            "AIzaSyCAfeF4c7ZkSLOJGqQcrmrOKP3k",
            "AIzaSyBJxWQi89F7jKmNzLDJHnlZ5DM8",
            "AIzaSyBXNVwk-w9vQGBjJlnqGxJIXg4",
            "AIzaSyB9QCgK1rQeNZF6CXL8WdOxjs",
            # ... 继续添加更多被暂停的密钥
        ]

        # 过滤掉被暂停的密钥
        valid_keys = []
        removed_count = 0

        for key_data in api_keys:
            if isinstance(key_data, str):
                key_value = key_data
            else:
                key_value = key_data.get('key', '')

            # 检查是否在暂停列表中
            is_suspended = any(suspended_key in key_value for suspended_key in suspended_keys)

            if not is_suspended:
                valid_keys.append(key_data)
            else:
                removed_count += 1
                print(f"🗑️  删除被暂停的密钥: {key_value[:15]}...")

        print(f"✅ 保留 {len(valid_keys)} 个有效密钥")
        print(f"🗑️  删除 {removed_count} 个被暂停密钥")

        # 更新数据库
        new_api_keys_json = json.dumps(valid_keys, ensure_ascii=False)
        cursor.execute(
            "UPDATE t_settings SET value = ? WHERE key = 'API_KEYS'",
            (new_api_keys_json,)
        )

        conn.commit()
        conn.close()

        print("✅ 数据库更新完成！")
        print("🔄 请重启服务以使更改生效")

    except Exception as e:
        print(f"❌ 清理过程中出错: {e}")

if __name__ == "__main__":
    clean_keys()
#!/usr/bin/env python3
"""
API密钥测试脚本
测试所有API密钥的有效性，并自动删除无效或被暂停的密钥
"""

import json
import asyncio
import aiohttp
import sqlite3
import sys
import os
from typing import List, Dict, Tuple
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Google API配置
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
TEST_MODEL = "gemini-2.0-flash"


class APIKeyTester:
    def __init__(self, db_path: str = "data/gemini_balance.db"):
        self.db_path = db_path
        # 从环境变量读取代理配置，如果未设置则使用默认值
        self.proxy_base_url = os.getenv('BASE_PROXY_URL', 'http://localhost:8080')
        self.valid_keys = []
        self.invalid_keys = []
        self.suspended_keys = []
        self.error_keys = []

    async def test_single_key(self, session: aiohttp.ClientSession, key_data: Dict) -> Tuple[Dict, str]:
        """测试单个API密钥"""
        if isinstance(key_data, str):
            api_key = key_data
            proxy_port = None
        else:
            api_key = key_data.get('key', '')
            proxy_port = key_data.get('proxy_port')

        # 构建代理URL
        proxy_url = None
        if proxy_port:
            proxy_url = f"{self.proxy_base_url}:{proxy_port}"

        # 构建请求URL
        url = f"{GEMINI_API_BASE}/models/{TEST_MODEL}:generateContent"

        # 请求头
        headers = {
            "Content-Type": "application/json"
        }

        # 请求体 - 简单的测试消息
        payload = {
            "contents": [{
                "parts": [{"text": "Hello"}]
            }],
            "generationConfig": {
                "maxOutputTokens": 10
            }
        }

        try:
            # 配置代理
            connector = None
            if proxy_url:
                connector = aiohttp.TCPConnector()

            # 发送请求
            params = {"key": api_key}

            timeout = aiohttp.ClientTimeout(total=30)
            async with session.post(
                url,
                json=payload,
                headers=headers,
                params=params,
                proxy=proxy_url if proxy_url else None,
                timeout=timeout
            ) as response:
                if response.status == 200:
                    return key_data, "valid"
                elif response.status == 403:
                    response_text = await response.text()
                    if "CONSUMER_SUSPENDED" in response_text or "suspended" in response_text.lower():
                        return key_data, "suspended"
                    else:
                        return key_data, "forbidden"
                elif response.status == 401:
                    return key_data, "invalid"
                elif response.status == 429:
                    return key_data, "quota_exceeded"
                else:
                    return key_data, f"error_{response.status}"

        except asyncio.TimeoutError:
            return key_data, "timeout"
        except Exception as e:
            return key_data, f"error_{str(e)[:50]}"

    async def test_all_keys(self, api_keys: List) -> None:
        """测试所有API密钥"""
        print(f"开始测试 {len(api_keys)} 个API密钥...")

        # 创建HTTP会话
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # 创建任务列表
            tasks = []
            for i, key_data in enumerate(api_keys):
                task = self.test_single_key(session, key_data)
                tasks.append(task)

                # 每10个密钥为一批，避免并发过高
                if len(tasks) == 10 or i == len(api_keys) - 1:
                    print(f"测试第 {i+1-len(tasks)+1} 到 {i+1} 个密钥...")

                    # 执行当前批次
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # 处理结果
                    for result in results:
                        if isinstance(result, Exception):
                            print(f"  错误: {result}")
                            continue

                        key_data, status = result
                        key_str = key_data if isinstance(key_data, str) else key_data.get('key', 'unknown')
                        key_display = f"{key_str[:10]}...{key_str[-4:]}" if len(key_str) > 14 else key_str

                        if status == "valid":
                            self.valid_keys.append(key_data)
                            print(f"  ✅ {key_display} - 有效")
                        elif status == "suspended":
                            self.suspended_keys.append(key_data)
                            print(f"  🚫 {key_display} - 已暂停")
                        elif status == "invalid":
                            self.invalid_keys.append(key_data)
                            print(f"  ❌ {key_display} - 无效")
                        elif status == "quota_exceeded":
                            # 配额超出的密钥仍然是有效的，只是暂时不可用
                            self.valid_keys.append(key_data)
                            print(f"  ⚠️  {key_display} - 配额超出(仍保留)")
                        else:
                            self.error_keys.append((key_data, status))
                            print(f"  ⚠️  {key_display} - 错误: {status}")

                    # 清空任务列表
                    tasks = []

                    # 短暂休息避免请求过快
                    await asyncio.sleep(1)

    def load_api_keys_from_db(self) -> List:
        """从数据库加载API密钥"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT value FROM t_settings WHERE key = 'API_KEYS'")
            result = cursor.fetchone()

            conn.close()

            if result and result[0]:
                api_keys = json.loads(result[0])
                print(f"从数据库加载了 {len(api_keys)} 个API密钥")
                return api_keys
            else:
                print("数据库中没有找到API密钥")
                return []

        except Exception as e:
            print(f"从数据库加载API密钥失败: {e}")
            return []

    def save_valid_keys_to_db(self) -> bool:
        """将有效的API密钥保存回数据库"""
        try:
            if not self.valid_keys:
                print("没有有效的API密钥可保存")
                return False

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 更新API_KEYS
            new_api_keys_json = json.dumps(self.valid_keys, ensure_ascii=False)
            cursor.execute(
                "UPDATE t_settings SET value = ? WHERE key = 'API_KEYS'",
                (new_api_keys_json,)
            )

            conn.commit()
            conn.close()

            print(f"✅ 已将 {len(self.valid_keys)} 个有效密钥保存到数据库")
            return True

        except Exception as e:
            print(f"❌ 保存API密钥到数据库失败: {e}")
            return False

    def print_summary(self):
        """打印测试结果摘要"""
        print("\n" + "="*60)
        print("📊 API密钥测试结果摘要")
        print("="*60)
        print(f"✅ 有效密钥: {len(self.valid_keys)}")
        print(f"🚫 已暂停密钥: {len(self.suspended_keys)}")
        print(f"❌ 无效密钥: {len(self.invalid_keys)}")
        print(f"⚠️  错误密钥: {len(self.error_keys)}")

        total_removed = len(self.suspended_keys) + len(self.invalid_keys) + len(self.error_keys)
        print(f"🗑️  已删除密钥: {total_removed}")

        if self.error_keys:
            print("\n错误详情:")
            for key_data, error in self.error_keys[:5]:  # 只显示前5个错误
                key_str = key_data if isinstance(key_data, str) else key_data.get('key', 'unknown')
                key_display = f"{key_str[:10]}...{key_str[-4:]}" if len(key_str) > 14 else key_str
                print(f"  {key_display}: {error}")
            if len(self.error_keys) > 5:
                print(f"  ... 还有 {len(self.error_keys) - 5} 个错误")

async def main():
    """主函数"""
    print("🔍 API密钥测试工具")
    print("="*40)

    tester = APIKeyTester()

    # 从数据库加载密钥
    api_keys = tester.load_api_keys_from_db()
    if not api_keys:
        print("没有找到API密钥，退出...")
        return

    # 测试所有密钥
    await tester.test_all_keys(api_keys)

    # 打印摘要
    tester.print_summary()

    # 询问是否保存结果
    if tester.valid_keys:
        response = input(f"\n是否将 {len(tester.valid_keys)} 个有效密钥保存到数据库并删除无效密钥? (y/N): ")
        if response.lower() in ['y', 'yes', 'Y']:
            success = tester.save_valid_keys_to_db()
            if success:
                print("✅ 数据库更新完成！请重启服务以使更改生效。")
            else:
                print("❌ 数据库更新失败！")
        else:
            print("❌ 已取消保存操作")
    else:
        print("❌ 没有有效的API密钥！")

if __name__ == "__main__":
    asyncio.run(main())
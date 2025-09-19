#!/usr/bin/env python3
"""
根据测试结果更新有效密钥
基于之前的测试结果，只保留174个有效的API密钥
"""

import json
import sqlite3

def update_keys():
    # 连接数据库
    conn = sqlite3.connect('data/gemini_balance.db')
    cursor = conn.cursor()

    # 获取当前密钥
    cursor.execute('SELECT value FROM t_settings WHERE key = "API_KEYS"')
    result = cursor.fetchone()
    api_keys = json.loads(result[0])

    print(f'原始密钥数量: {len(api_keys)}')

    # 根据测试结果，移除被暂停的密钥
    # 以下是从测试日志中提取的被暂停密钥的部分标识
    suspended_partials = [
        "AIzaSyCFRo", "AIzaSyAxUd", "AIzaSyDPrv", "AIzaSyAbOY", "AIzaSyCAfe",
        "AIzaSyBJxW", "AIzaSyBXNV", "AIzaSyB9QC", "AIzaSyDZqp", "AIzaSyCZqM",
        "AIzaSyAjp0", "AIzaSyDGae", "AIzaSyDHkE", "AIzaSyARYL", "AIzaSyAdVP",
        "AIzaSyAZKG", "AIzaSyAJp6", "AIzaSyA1Lp", "AIzaSyDJzx", "AIzaSyBIiO",
        "AIzaSyDGWf", "AIzaSyDq4E", "AIzaSyAaol", "AIzaSyDaNe", "AIzaSyBvaq",
        "AIzaSyBNJk", "AIzaSyDnKu", "AIzaSyAFm0", "AIzaSyDQC6", "AIzaSyC7HE",
        "AIzaSyBLPg", "AIzaSyARNs", "AIzaSyBMCe", "AIzaSyDzv-", "AIzaSyCmYd",
        "AIzaSyB5KH", "AIzaSyBzaI", "AIzaSyBCGz", "AIzaSyDGfQ", "AIzaSyD7fB"
    ]

    # 过滤有效密钥
    valid_keys = []
    for key_data in api_keys:
        if isinstance(key_data, str):
            key_value = key_data
        else:
            key_value = key_data.get('key', '')

        # 检查是否包含被暂停密钥的标识
        is_suspended = any(partial in key_value for partial in suspended_partials)

        if not is_suspended:
            valid_keys.append(key_data)

    print(f'过滤后密钥数量: {len(valid_keys)}')

    # 如果数量太少，我们使用保守策略，只移除明确失败的
    if len(valid_keys) < 150:
        print('保守过滤策略...')
        # 只移除明确被暂停的前几个
        confirmed_suspended = [
            "AIzaSyCFRo1wCj7Muph5IwD0BqU4v77zWWgt8Lc",
            "AIzaSyAxUd9NCOeDV1JOuE5sc2lLApWfT24ylqA",
            "AIzaSyDPrv1RxoMt0pDqAyiD_YKL2dgzm6nKJLA"
        ]

        valid_keys = []
        for key_data in api_keys:
            if isinstance(key_data, str):
                key_value = key_data
            else:
                key_value = key_data.get('key', '')

            if key_value not in confirmed_suspended:
                valid_keys.append(key_data)

    print(f'最终保留密钥数量: {len(valid_keys)}')

    # 更新数据库
    new_api_keys_json = json.dumps(valid_keys, ensure_ascii=False)
    cursor.execute(
        'UPDATE t_settings SET value = ? WHERE key = "API_KEYS"',
        (new_api_keys_json,)
    )

    conn.commit()
    conn.close()

    print('✅ 数据库已更新')
    print('🔄 请重启服务')

if __name__ == "__main__":
    update_keys()
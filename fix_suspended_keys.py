#!/usr/bin/env python3
"""
Direct fix for suspended API keys issue
This script will forcefully remove all suspended keys from the database
"""

import sqlite3
import json

def fix_suspended_keys():
    # The exact suspended key that's causing the problem
    suspended_key = 'AIzaSyCFRo1wCj7Muph5IwD0BqU4v77zWWgt8Lc'

    # Additional suspended key partials
    suspended_partials = [
        'AIzaSyCFRo', 'AIzaSyAxUd', 'AIzaSyDPrv', 'AIzaSyAbOY', 'AIzaSyCAfe',
        'AIzaSyBJxW', 'AIzaSyBXNV', 'AIzaSyB9QC', 'AIzaSyDZqp', 'AIzaSyCZqM',
        'AIzaSyAjp0', 'AIzaSyDGae', 'AIzaSyDHkE', 'AIzaSyARYL', 'AIzaSyAdVP',
        'AIzaSyAZKG', 'AIzaSyAJp6', 'AIzaSyA1Lp', 'AIzaSyDJzx', 'AIzaSyBIiO',
        'AIzaSyDGWf', 'AIzaSyDq4E', 'AIzaSyAaol', 'AIzaSyDaNe', 'AIzaSyBvaq',
        'AIzaSyBNJk', 'AIzaSyDnKu', 'AIzaSyAFm0', 'AIzaSyDQC6', 'AIzaSyC7HE',
        'AIzaSyBLPg', 'AIzaSyARNs', 'AIzaSyBMCe', 'AIzaSyDzv-', 'AIzaSyCmYd',
        'AIzaSyB5KH', 'AIzaSyBzaI', 'AIzaSyBCGz', 'AIzaSyDGfQ', 'AIzaSyD7fB'
    ]

    print("🔧 Fixing suspended API keys issue...")

    # Connect to database
    conn = sqlite3.connect('data/gemini_balance.db')
    cursor = conn.cursor()

    # Get current API keys
    cursor.execute('SELECT value FROM t_settings WHERE key = "API_KEYS"')
    result = cursor.fetchone()

    if not result or not result[0]:
        print("❌ No API_KEYS found in database")
        return False

    api_keys = json.loads(result[0])
    print(f"📊 Original API keys count: {len(api_keys)}")

    # Filter out suspended keys
    valid_keys = []
    removed_count = 0

    for key_data in api_keys:
        if isinstance(key_data, str):
            key_value = key_data
        else:
            key_value = key_data.get('key', '')

        # Check if this key is suspended
        is_suspended = False

        # Check exact match first
        if suspended_key in key_value:
            is_suspended = True
            print(f"🗑️  Removing exact suspended key: {key_value[:20]}...")

        # Check partial matches
        if not is_suspended:
            for partial in suspended_partials:
                if partial in key_value:
                    is_suspended = True
                    print(f"🗑️  Removing suspended key (partial {partial}): {key_value[:20]}...")
                    break

        if not is_suspended:
            valid_keys.append(key_data)
        else:
            removed_count += 1

    print(f"✅ Filtered API keys count: {len(valid_keys)}")
    print(f"🗑️  Removed {removed_count} suspended keys")

    if removed_count == 0:
        print("ℹ️  No suspended keys found to remove")
        conn.close()
        return True

    # Update database with new keys
    new_api_keys_json = json.dumps(valid_keys, ensure_ascii=False)
    cursor.execute(
        'UPDATE t_settings SET value = ? WHERE key = "API_KEYS"',
        (new_api_keys_json,)
    )

    # Verify the update
    cursor.execute('SELECT value FROM t_settings WHERE key = "API_KEYS"')
    verify_result = cursor.fetchone()
    verify_keys = json.loads(verify_result[0])

    print(f"🔍 Verification: Database now has {len(verify_keys)} keys")

    # Double check the suspended key is gone
    found_suspended = False
    for key_data in verify_keys:
        if isinstance(key_data, str):
            key_value = key_data
        else:
            key_value = key_data.get('key', '')

        if suspended_key in key_value:
            found_suspended = True
            break

    if found_suspended:
        print("❌ ERROR: Suspended key still found after update!")
        conn.rollback()
        conn.close()
        return False
    else:
        print("✅ SUCCESS: Suspended key completely removed!")
        conn.commit()
        conn.close()
        return True

if __name__ == "__main__":
    success = fix_suspended_keys()
    if success:
        print("\n🎉 API keys successfully cleaned!")
        print("🔄 Please restart the service now")
    else:
        print("\n❌ Failed to clean API keys")
#!/usr/bin/env python3
"""
Migration script to extract active API keys and proxy ports from gemini2openai repository
"""
import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Union

def read_apiinfo_csv(csv_path: str) -> List[Dict]:
    """Read and parse the apiinfo.csv file"""
    active_keys = []

    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Check if key is active (state=ok) and has a proxy port
                if (row.get('state') == 'ok' and
                    row.get('proxy_port') and
                    row.get('proxy_port').strip() and
                    row.get('api_key')):

                    try:
                        proxy_port = int(float(row['proxy_port']))
                        active_keys.append({
                            'key': row['api_key'].strip(),
                            'proxy_port': proxy_port
                        })
                    except (ValueError, TypeError):
                        print(f"Skipping key with invalid proxy_port: {row.get('proxy_port')}")
                        continue
    except FileNotFoundError:
        print(f"Error: CSV file not found at {csv_path}")
        return []
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return []

    return active_keys

def format_api_keys(active_keys: List[Dict]) -> str:
    """Format API keys for the .env file"""
    if not active_keys:
        return '[]'

    # Create JSON array with proper formatting
    keys_array = []
    for key_info in active_keys:
        keys_array.append({
            "key": key_info['key'],
            "proxy_port": key_info['proxy_port']
        })

    # Format as compact JSON
    return json.dumps(keys_array, separators=(',', ':'))

def update_env_file(env_path: str, api_keys_str: str, base_proxy_url: str) -> None:
    """Update the .env file with new API_KEYS configuration"""
    env_lines = []
    api_keys_updated = False
    base_proxy_updated = False

    # Read existing .env file if it exists
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as file:
            env_lines = file.readlines()

    # Update or add API_KEYS and BASE_PROXY_URL
    new_lines = []
    for line in env_lines:
        line = line.strip()
        if line.startswith('API_KEYS='):
            new_lines.append(f'API_KEYS={api_keys_str}\n')
            api_keys_updated = True
        elif line.startswith('BASE_PROXY_URL='):
            new_lines.append(f'BASE_PROXY_URL={base_proxy_url}\n')
            base_proxy_updated = True
        else:
            new_lines.append(line + '\n' if line else '\n')

    # Add missing configurations
    if not api_keys_updated:
        new_lines.append(f'API_KEYS={api_keys_str}\n')
    if not base_proxy_updated:
        new_lines.append(f'BASE_PROXY_URL={base_proxy_url}\n')

    # Write updated .env file
    with open(env_path, 'w', encoding='utf-8') as file:
        file.writelines(new_lines)

def main():
    """Main migration function"""
    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    gemini2openai_path = Path("/home/trader/repos/gemini2openai/apiinfo.csv")
    env_path = project_root / ".env"

    print("Starting API keys migration...")
    print(f"Reading from: {gemini2openai_path}")
    print(f"Updating: {env_path}")

    # Read active keys from CSV
    active_keys = read_apiinfo_csv(str(gemini2openai_path))

    if not active_keys:
        print("No active API keys found!")
        sys.exit(1)

    print(f"Found {len(active_keys)} active API keys with proxy ports")

    # Show first few keys as preview
    print("\nPreview of first 3 keys:")
    for i, key_info in enumerate(active_keys[:3]):
        masked_key = key_info['key'][:12] + "..." + key_info['key'][-4:]
        print(f"  {i+1}. {masked_key} -> proxy port {key_info['proxy_port']}")

    # Format API keys
    api_keys_str = format_api_keys(active_keys)
    base_proxy_url = "http://sp1w0pmdkq:SF6so4rdDj3vSq=r3l@dc.decodo.com:{port}"

    # Update .env file
    try:
        update_env_file(str(env_path), api_keys_str, base_proxy_url)
        print(f"\nSuccessfully updated {env_path}")
        print(f"Migrated {len(active_keys)} API keys with proxy configuration")
        print("\nNext steps:")
        print("1. Review the updated .env file")
        print("2. Start the application to test the new configuration")
    except Exception as e:
        print(f"Error updating .env file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
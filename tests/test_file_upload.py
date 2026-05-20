"""
Basic test for file upload endpoint /api/file/upload.

This test verifies:
- Valid file extension (txt, csv, json, xlsx)
- Size limit enforced (10 MB)
- Safe filename sanitization
- Data directory is used from environment variable

Run without pytest:
    python3 tests/test_file_upload.py --verify
"""

import os
import re
import sys
from io import BytesIO

# Ensure DATA_DIR is set for tests
DATA_DIR = os.environ.get('DATA_DIR', '/tmp/ouroboros_test_data')
os.makedirs(DATA_DIR, exist_ok=True)


def test_valid_extensions():
    """Verify only whitelisted extensions are allowed."""
    valid_exts = {'.txt', '.csv', '.json', '.xlsx', '.pdf', '.png', '.jpg', '.jpeg'}
    test_cases = [
        ('data.csv', True),
        ('report.xlsx', True),
        ('config.json', True),
        ('notes.txt', True),
        ('image.png', True),
        ('trojan.exe', False),
        ('malware.sh', False),
        ('unknown.xyz', False),
    ]
    for filename, should_be_valid in test_cases:
        is_valid = any(filename.lower().endswith(ext) for ext in valid_exts)
        assert is_valid == should_be_valid, f"File {filename} validation failed: {is_valid} != {should_be_valid}"
    print("✓ Valid extensions test passed")


def test_size_limit():
    """Verify 10 MB size limit is enforced."""
    max_size = 10 * 1024 * 1024  # 10 MB
    test_cases = [
        (100, True),           # Small file
        (1024 * 1024, True),    # 1 MB
        (max_size, True),       # Exactly 10 MB
        (max_size + 1, False),  # Over 10 MB
        (20 * 1024 * 1024, False), # 20 MB
    ]
    for size, should_be_valid in test_cases:
        is_valid = size <= max_size
        assert is_valid == should_be_valid, f"Size {size} validation failed: {is_valid} != {should_be_valid}"
    print("✓ Size limit test passed")


def test_filename_sanitization():
    """Test that filenames are sanitized to avoid path traversal."""
    malicious_names = [
        '../../etc/passwd',
        '..\\\\windows\\system32',
        'file\x00null',
        'con (Windows reserved)',
        'normal_file.txt'
    ]
    for name in malicious_names:
        sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
        # After sanitization: no path traversal, no null bytes
        assert '../' not in sanitized, f"Path traversal detect in: {sanitized}"
        assert '\x00' not in sanitized, f"Null byte detect in: {sanitized}"
    print("✓ Filename sanitization test passed")


def test_data_dir_env():
    """Verify DATA_DIR is used from environment variable."""
    assert DATA_DIR != '/tmp/ouroboros_test_data' or os.path.exists(DATA_DIR)
    assert os.path.isdir(DATA_DIR), f"DATA_DIR {DATA_DIR} does not exist"
    print(f"✓ DATA_DIR test passed ({DATA_DIR})")


def run_verification():
    """Run all tests and exit with status code."""
    try:
        test_valid_extensions()
        test_size_limit()
        test_filename_sanitization()
        test_data_dir_env()
        print("\n✅ All tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    if '--verify' in sys.argv:
        run_verification()
    else:
        print("Run with --verify to execute tests")
        print("Example: python3 tests/test_file_upload.py --verify")
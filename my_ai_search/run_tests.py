#!/usr/bin/env python3
"""
运行所有模块的测试
"""

import sys
import subprocess
import os


def run_test(test_file):
    """运行单个测试文件"""
    print(f"\n{'=' * 60}")
    print(f"Running {test_file}")
    print(f"{'=' * 60}")

    result = subprocess.run(
        [sys.executable, test_file],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode == 0


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("AI Search - Running All Tests")
    print("=" * 60)

    test_files = [
        "test_utils.py",
        "test_config.py",
        "test_search.py",
        "test_fetch.py",
        "test_process.py",
        "test_deep_process.py",
        "test_vector_query.py",
    ]

    results = {}
    for test_file in test_files:
        if os.path.exists(test_file):
            results[test_file] = run_test(test_file)
        else:
            print(f"Warning: {test_file} not found")
            results[test_file] = False

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(results.values())
    total = len(results)

    for test_file, passed_flag in results.items():
        status = "✓ PASSED" if passed_flag else "✗ FAILED"
        print(f"{status:12s} - {test_file}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if all(results.values()):
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

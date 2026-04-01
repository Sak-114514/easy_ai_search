"""
测试运行脚本
"""

import subprocess
import sys
from pathlib import Path


def run_tests(test_type="all", coverage=False, verbose=False):
    """
    运行测试

    Args:
        test_type: 测试类型 (all, unit, integration)
        coverage: 是否生成覆盖率报告
        verbose: 是否显示详细输出
    """
    project_root = Path(__file__).parent.parent

    # 切换到项目根目录
    import os

    os.chdir(project_root)

    # 构建pytest命令
    cmd = ["python", "-m", "pytest", "api_server/tests/"]

    # 添加测试类型过滤
    if test_type == "unit":
        cmd.extend(["-k", "not integration"])
    elif test_type == "integration":
        cmd.extend(["-k", "integration"])

    # 添加覆盖率选项
    if coverage:
        cmd.extend(
            [
                "--cov=api_server",
                "--cov-report=html",
                "--cov-report=term-missing",
            ]
        )

    # 添加详细输出
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # 运行测试
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    # 输出覆盖率报告位置
    if coverage and result.returncode == 0:
        print("\nCoverage report generated at: htmlcov/index.html")

    return result.returncode


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="运行API Server测试")
    parser.add_argument(
        "--type",
        choices=["all", "unit", "integration"],
        default="all",
        help="测试类型",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="生成覆盖率报告",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="显示详细输出",
    )

    args = parser.parse_args()

    returncode = run_tests(
        test_type=args.type,
        coverage=args.coverage,
        verbose=args.verbose,
    )

    sys.exit(returncode)


if __name__ == "__main__":
    main()

"""
启动脚本
"""

import uvicorn
from api_server.config import get_api_config


def main():
    """启动 API Server"""
    config = get_api_config()

    uvicorn.run(
        "api_server.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()

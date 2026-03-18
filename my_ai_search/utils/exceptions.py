class AISearchException(Exception):
    """
    AI搜索项目基础异常类
    所有自定义异常都继承自此类
    """

    def __init__(self, message: str = "An error occurred in AI Search"):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message


class ConfigException(AISearchException):
    """配置相关异常"""

    def __init__(self, message: str = "Configuration error"):
        super().__init__(f"Config Error: {message}")


class SearchException(AISearchException):
    """搜索层异常"""

    def __init__(self, message: str = "Search operation failed"):
        super().__init__(f"Search Error: {message}")


class FetchException(AISearchException):
    """抓取层异常"""

    def __init__(self, url: str = "", message: str = "Failed to fetch page"):
        if url:
            super().__init__(f"Fetch Error [{url}]: {message}")
        else:
            super().__init__(f"Fetch Error: {message}")


class ProcessException(AISearchException):
    """处理层异常"""

    def __init__(self, message: str = "Content processing failed"):
        super().__init__(f"Process Error: {message}")


class VectorException(AISearchException):
    """向量层异常"""

    def __init__(self, message: str = "Vector operation failed"):
        super().__init__(f"Vector Error: {message}")


class CacheException(AISearchException):
    """缓存层异常"""

    def __init__(self, message: str = "Cache operation failed"):
        super().__init__(f"Cache Error: {message}")


class DeepProcessException(AISearchException):
    """深度处理层异常"""

    def __init__(self, message: str = "Deep process operation failed"):
        super().__init__(f"Deep Process Error: {message}")

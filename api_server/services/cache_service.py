"""
缓存服务
"""

from typing import Dict, Optional
from my_ai_search.cache import get_cache_stats, clear_cache, is_cached


class CacheService:
    """缓存服务类"""

    def get_stats(self) -> Dict:
        """
        获取缓存统计信息

        Returns:
            缓存统计字典
        """
        return get_cache_stats()

    def clear_cache(self) -> Dict:
        """
        清空缓存

        Returns:
            清空结果
        """
        try:
            stats = get_cache_stats()
            clear_cache()
            return {
                "success": True,
                "cleared": stats.get("total", 0),
                "message": "Cache cleared successfully",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_cache(self, url: str) -> Dict:
        """
        检查URL是否在缓存中

        Args:
            url: URL地址

        Returns:
            缓存检查结果
        """
        try:
            cached = is_cached(url)
            return {
                "cached": cached,
                "url": url,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "url": url,
            }

    def get_hit_rate(self) -> Dict:
        """
        获取缓存命中率

        Returns:
            命中率信息
        """
        try:
            stats = get_cache_stats()
            total = stats.get("total", 0)
            hits = stats.get("hits", 0)

            hit_rate = 0.0
            if total > 0:
                hit_rate = hits / total

            return {
                "total": total,
                "hits": hits,
                "misses": total - hits,
                "hit_rate": round(hit_rate * 100, 2),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

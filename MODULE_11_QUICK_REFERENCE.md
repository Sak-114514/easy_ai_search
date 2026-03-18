# 模块11快速参考

## 导入语句模板

```python
import sys
import time
import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime

from config import get_config, validate_config
from utils.logger import setup_logger

# 搜索层
from search.search import search

# 抓取层
from fetch.fetch_concurrent import fetch_pages_sync

# 处理层
from process.process import process_content

# 深度处理层
from deep_process.deep_process import deep_process_content

# 向量层
from vector.vector import init_vector_db, store_documents, get_collection_stats
from vector.vector_query import hybrid_search

# 缓存层（可选）
try:
    from cache.cache import set_cache, get_cached, is_cached, get_cache_stats
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
```

## 核心函数调用速查

### 1. 配置验证
```python
config = get_config()
if not validate_config(config):
    raise Exception("Configuration validation failed")
```

### 2. 初始化向量库
```python
init_vector_db()
```

### 3. 搜索URL
```python
search_results = search(query, max_results=max_results)
# 返回: List[{title, url, content}]
```

### 4. 抓取页面
```python
urls = [r['url'] for r in search_results]
fetch_results = fetch_pages_sync(urls)
# 返回: List[{url, html, title, success, error, from_cache}]
```

### 5. 处理内容
```python
all_chunks = []
for fetch_result in fetch_results:
    if fetch_result['success']:
        chunks = process_content(fetch_result['html'], url=fetch_result['url'])
        all_chunks.extend(chunks)
# 返回: List[{text, metadata, chunk_id}]
```

### 6. 深度处理
```python
config = get_config()
deep_processed_chunks = deep_process_content(
    all_chunks,
    enable_summary=config.deep_process.enable_summary,
    enable_dedup=config.deep_process.enable_dedup,
    enable_quality_check=config.deep_process.enable_quality_check
)
# 返回: List[{text, metadata, quality_score, summary}]
```

### 7. 存储文档
```python
document_ids = store_documents(deep_processed_chunks)
# 返回: List[document_id]
```

### 8. 检索
```python
vector_results = hybrid_search(query, top_k=max_results)
# 返回: List[{text, similarity, score, metadata}]
```

### 9. 缓存操作（可选）
```python
# 检查缓存
if is_cached(url):
    cached = get_cached(url)

# 设置缓存
set_cache(url, html, title)

# 获取统计
stats = get_cache_stats()
```

## 数据格式速查

### 搜索结果格式
```python
{
    'title': str,
    'url': str,
    'content': str
}
```

### 抓取结果格式
```python
{
    'url': str,
    'html': str,
    'title': str,
    'success': bool,
    'error': Optional[str],
    'from_cache': bool
}
```

### 处理结果格式
```python
{
    'text': str,
    'metadata': {
        'source_url': str,
        'chunk_id': int,
        'title': str
    }
}
```

### 深度处理结果格式
```python
{
    'text': str,
    'metadata': {
        'source_url': str,
        'chunk_id': int,
        'title': str,
        'quality_score': float,
        'summary': str
    }
}
```

### 检索结果格式
```python
{
    'text': str,
    'similarity': float,
    'score': float,
    'metadata': dict
}
```

### 最终输出格式
```python
{
    'query': str,
    'results': [
        {
            'title': str,
            'url': str,
            'cleaned_content': str,
            'similarity_score': float,
            'metadata': dict
        }
    ],
    'total_time': float,
    'cache_stats': dict,
    'search_stats': dict,
    'fetch_stats': dict,
    'process_stats': dict,
    'deep_process_stats': dict,
    'vector_stats': dict
}
```

## 错误处理模板

```python
try:
    # 步骤操作
    result = some_function()
    logger.info(f"Step completed: {result}")
except SearchException as e:
    logger.error(f"Search failed: {e}")
    # 处理错误，继续或返回
except FetchException as e:
    logger.error(f"Fetch failed: {e}")
    # 处理错误，继续或返回
except ProcessException as e:
    logger.error(f"Process failed: {e}")
    # 处理错误，继续或返回
except VectorException as e:
    logger.error(f"Vector operation failed: {e}")
    # 处理错误，继续或返回
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

## 统计信息收集模板

```python
# 搜索统计
search_stats = {
    'urls_found': len(search_results),
    'time': step1_time
}

# 抓取统计
fetch_stats = {
    'total': len(urls),
    'success': successful_fetches,
    'failed': len(urls) - successful_fetches,
    'cache_hits': cache_hits,
    'time': step2_time
}

# 处理统计
process_stats = {
    'chunks': len(all_chunks),
    'time': step3_time
}

# 深度处理统计
deep_process_stats = {
    'chunks': len(deep_processed_chunks),
    'removed_duplicates': removed_duplicates,
    'filtered_low_quality': filtered_low_quality,
    'time': step4_time
}

# 向量统计
vector_stats = {
    'stored_documents': len(document_ids),
    'retrieved_results': len(vector_results),
    'time': step5_time + step6_time
}
```

## 命令行参数处理模板

```python
import argparse

parser = argparse.ArgumentParser(description='AI Search - Local AI-powered search engine')
parser.add_argument('query', type=str, help='Search query')
parser.add_argument('--max-results', type=int, default=5,
                   help='Maximum number of results')
parser.add_argument('--no-cache', action='store_true',
                   help='Disable cache')
parser.add_argument('--format', choices=['json', 'pretty'], default='pretty',
                   help='Output format')

args = parser.parse_args()

# 使用参数
query = args.query
max_results = args.max_results
use_cache = not args.no_cache
output_format = args.format
```

## 日志记录模板

```python
logger = setup_logger("main")

# 关键步骤
logger.info(f"Starting AI search: query='{query}', max_results={max_results}")
logger.info(f"Found {len(search_results)} URLs")
logger.info(f"Fetched {successful_fetches}/{len(urls)} pages")
logger.info(f"Generated {len(all_chunks)} chunks")
logger.info(f"Deep processing: {len(all_chunks)} -> {len(deep_processed_chunks)} chunks")
logger.info(f"AI search completed in {total_time:.2f}s")

# 警告信息
logger.warning("No search results found")
logger.warning("No content chunks generated")

# 错误信息
logger.error(f"AI search failed: {e}")
```

## 性能监控模板

```python
import time

# 记录开始时间
start_time = time.time()

# 步骤1
step1_start = time.time()
# 执行操作
search_results = search(query)
step1_time = time.time() - step1_start

# 步骤2
step2_start = time.time()
# 执行操作
fetch_results = fetch_pages_sync(urls)
step2_time = time.time() - step2_start

# ... 其他步骤

# 总时间
total_time = time.time() - start_time
```

## 缓存集成模板

```python
# 带缓存的抓取
fetch_results = []
cache_hits = 0

if use_cache and CACHE_AVAILABLE:
    for url in urls:
        if is_cached(url):
            logger.info(f"Cache hit: {url}")
            cached = get_cached(url)
            fetch_results.append({
                'url': url,
                'html': cached['html'],
                'title': cached['title'],
                'success': True,
                'error': None,
                'from_cache': True
            })
            cache_hits += 1
        else:
            fetch_results.append({'url': url, 'success': False})

    # 只抓取未缓存的URL
    uncached_urls = [r['url'] for r in fetch_results if not r.get('from_cache')]
    if uncached_urls:
        uncached_results = fetch_pages_sync(uncached_urls)
        for i, result in enumerate(uncached_results):
            url = uncached_urls[i]
            if result['success']:
                for r in fetch_results:
                    if r['url'] == url:
                        r.update(result)
                        break
                set_cache(url, result['html'], result['title'])
else:
    fetch_results = fetch_pages_sync(urls)
```

## 结果构建模板

```python
final_results = []
for vector_result in vector_results:
    source_url = vector_result['metadata'].get('source_url', '')
    chunk_id = vector_result['metadata'].get('chunk_id', 0)

    original_result = next(
        (r for r in search_results if r['url'] == source_url),
        None
    )

    final_results.append({
        'title': original_result['title'] if original_result else vector_result['text'][:50],
        'url': source_url,
        'cleaned_content': vector_result['text'],
        'similarity_score': vector_result.get('score', vector_result['similarity']),
        'metadata': {
            'chunk_id': chunk_id,
            'vector_similarity': vector_result['similarity'],
            'hybrid_score': vector_result.get('score', 0)
        }
    })
```

## 完整流程伪代码

```python
def search_ai(query, max_results=None, use_cache=True):
    start_time = time.time()

    # 1. 验证配置
    config = get_config()
    if not validate_config(config):
        raise Exception("Config validation failed")

    # 2. 初始化向量库
    init_vector_db()

    # 3. 搜索URL
    search_results = search(query, max_results=max_results)

    # 4. 抓取页面（带缓存）
    urls = [r['url'] for r in search_results]
    fetch_results = fetch_with_cache(urls, use_cache)

    # 5. 处理内容
    all_chunks = []
    for result in fetch_results:
        if result['success']:
            chunks = process_content(result['html'], url=result['url'])
            all_chunks.extend(chunks)

    # 6. 深度处理
    deep_processed_chunks = deep_process_content(all_chunks)

    # 7. 存储文档
    document_ids = store_documents(deep_processed_chunks)

    # 8. 检索
    vector_results = hybrid_search(query, top_k=max_results)

    # 9. 构建结果
    final_results = build_final_results(vector_results, search_results)

    # 10. 返回
    return {
        'query': query,
        'results': final_results,
        'total_time': time.time() - start_time,
        'stats': {...}
    }
```

---

**快速参考版本**: 1.0
**创建日期**: 2026-03-18

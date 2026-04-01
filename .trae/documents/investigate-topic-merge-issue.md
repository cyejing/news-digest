# 排查 merge-hotspots topic 内容错乱问题

## 用户预设逻辑

1. **merge-sources.py**：输出的 JSON 按 source\_type 分组，并且按 final\_score 排序
2. **merge-hotspots.py**：根据 topic 分组时，分别从各个 source\_type 中取符合该 topic 的评分第一个出来，放进 topic 分组，直到该 topic 满足限额
3. **预期效果**：每个 topic 分组的 source\_type 都是多样性的

## 实际发现的问题

**topic 分组里面有非该 topic 的数据**

## 问题根因分析

### **核心问题：重复文章合并时 topic 被错误覆盖**

在 `merge-sources.py` 的 `merge_cluster_metadata` 函数中（第 731-751 行）：

```python
def merge_cluster_metadata(canonical: Dict[str, Any], cluster_articles: List[Dict[str, Any]], cluster_id: int) -> Dict[str, Any]:
    # ... 省略其他代码 ...
    
    merged_topic = resolve_cluster_topic(cluster_articles, default=resolve_article_topic(canonical, ""))
    if merged_topic:
        canonical["topic"] = merged_topic
    return canonical
```

**问题分析**：

`resolve_cluster_topic` 函数会从 cluster\_articles 中选择第一个有 topic 的文章的 topic：

```python
def resolve_cluster_topic(cluster_articles: List[Dict[str, Any]], default: str = "") -> str:
    for article in cluster_articles:
        topic = resolve_article_topic(article)
        if topic:
            return topic  # 返回第一个有 topic 的文章的 topic
    return default
```

**问题场景**：

1. 文章 A：topic="ai-frontier", final\_score=10.0
2. 文章 B：topic="ai-infra", final\_score=9.0 (与文章 A 相似)
3. 在去重阶段，文章 A 和 B 被合并到一个 cluster
4. canonical 是文章 A（因为分数更高）
5. 但 `resolve_cluster_topic` 可能返回文章 B 的 topic="ai-infra"（如果文章 B 在 cluster\_articles 列表中排在前面）
6. 结果：文章 A 的 topic 被改成 "ai-infra"

**导致的问题**：

* 在 merge-hotspots 阶段，文章 A 会被归类到 "ai-infra" topic

* 但文章 A 的内容实际上是 "ai-frontier" 相关的

* 这就是为什么 topic 分组里面有非该 topic 的数据

## merge-hotspots.py 的逻辑验证

我验证了 `merge-hotspots.py` 的逻辑，**它是正确的**：

1. `build_topic_candidates` 函数（第 125-168 行）：

   * 遍历所有 source\_type 和文章

   * 根据文章的 `topic` 字段将文章分组到 `topic_candidates[topic_id][source_type]`

   * 逻辑正确：`topic_id = str(article.get("topic") or "uncategorized")`

2. `select_topic_articles` 函数（第 171-198 行）：

   * 从 `topic_source_candidates` 中轮转选择文章

   * 逻辑正确：只从 `topic_source_candidates` 中选择，不会混入其他 topic 的文章

**结论**：merge-hotspots.py 的逻辑与用户预设一致，问题出在 merge-sources.py 的 topic 合并逻辑。

## 修复方案

### 修复 `merge_cluster_metadata` 函数

**原则**：canonical 文章的 topic 应该优先保留，不应该被相似文章的 topic 覆盖。

**修复代码**：

```python
def merge_cluster_metadata(canonical: Dict[str, Any], cluster_articles: List[Dict[str, Any]], cluster_id: int) -> Dict[str, Any]:
    unique_sources = []
    seen = set()
    for article in cluster_articles:
        source_name = article.get("source_name") or article.get("source_id") or article.get("source_type")
        if source_name and source_name not in seen:
            seen.add(source_name)
            unique_sources.append(source_name)

    canonical["multi_source"] = len({a.get("source_type") for a in cluster_articles}) > 1
    canonical["source_name_count"] = len(unique_sources)
    canonical["source_names"] = unique_sources[:5]
    canonical["similarity_debug"]["duplicate_group"] = {
        "merged": len(cluster_articles) > 1,
        "cluster_size": len(cluster_articles),
    }

    # 修复：优先保留 canonical 文章的 topic
    canonical_topic = resolve_article_topic(canonical)
    if canonical_topic:
        # canonical 文章有明确的 topic，保持不变
        pass
    else:
        # canonical 文章没有 topic，尝试从 cluster 中获取
        merged_topic = resolve_cluster_topic(cluster_articles, default="")
        if merged_topic:
            canonical["topic"] = merged_topic
    
    return canonical
```

## 验证方案

1. **添加测试用例**：验证当相似文章有不同 topic 时，canonical 文章的 topic 不会被覆盖
2. **运行现有测试**：确保修复不会破坏现有功能
3. **使用实际数据测试**：运行 pipeline，检查 topic 分组是否正确

## 实施步骤

1. 修复 `merge_cluster_metadata` 函数
2. 添加测试用例验证修复效果
3. 运行测试确保没有破坏现有功能


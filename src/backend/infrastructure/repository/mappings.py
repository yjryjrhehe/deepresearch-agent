from ...core.config import settings

# 从配置获取维度，保证动态性
EMBEDDING_DIM = settings.embedding_llm.dimension

def get_opensearch_mapping() -> dict:
    """
    获取 OpenSearch 索引映射配置。
    封装在函数中可以更方便地动态注入参数。
    """
    return {
        "settings": {
            "index": {
                "knn": True
            }
        },
        "mappings": {
            "properties": {
                # === 1. 关键索引字段 ===
                "chunk_id": {
                    "type": "keyword" 
                },
                "document_id": {
                    "type": "keyword" 
                },
                
                # === 2. 文本字段 (用于 BM25 和存储) ===
                "document_name": {
                    "type": "text",
                    "analyzer": "standard"
                },
                "content": {
                    "type": "text",
                    "analyzer": "standard" 
                },
                "content_tokenized": { 
                    "type": "text",
                    "analyzer": "whitespace" 
                },
                "parent_headings_merged": { 
                    "type": "text",
                    "analyzer": "standard" 
                },
                "summary": {
                    "type": "text",
                    "analyzer": "standard" 
                },
                "hypothetical_questions_merged": {
                    "type": "text",
                    "analyzer": "standard" 
                },

                # === 3. 向量索引字段 ===
                "embedding_content": {
                    "type": "knn_vector",
                    "dimension": EMBEDDING_DIM,
                    "method": {
                        "name": "hnsw",
                        "engine": "faiss", 
                        "space_type": "cosinesimil", 
                        "parameters": {
                            "ef_construction": 256,
                            "m": 48
                        }
                    }
                },
                "embedding_parent_headings": {
                    "type": "knn_vector",
                    "dimension": EMBEDDING_DIM,
                    "method": {
                        "name": "hnsw",
                        "engine": "faiss",
                        "space_type": "cosinesimil",
                        "parameters": {
                            "ef_construction": 256,
                            "m": 48
                        }
                    }
                },
                "embedding_summary": {
                    "type": "knn_vector",
                    "dimension": EMBEDDING_DIM,
                    "method": {
                        "name": "hnsw",
                        "engine": "faiss",
                        "space_type": "cosinesimil",
                        "parameters": {
                            "ef_construction": 256,
                            "m": 48
                        }
                    }
                },
                "embedding_hypothetical_questions": {
                    "type": "knn_vector",
                    "dimension": EMBEDDING_DIM,
                    "method": {
                        "name": "hnsw",
                        "engine": "faiss",
                        "space_type": "cosinesimil",
                        "parameters": {
                            "ef_construction": 256,
                            "m": 48
                        }
                    }
                },

                # === 4. 元数据 ===
                "metadata": {
                    "type": "object",
                    "enabled": False 
                }
            }
        }
    }
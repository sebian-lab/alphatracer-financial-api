"""
Fuzzy string matching utilities.
Implements Levenshtein distance and various similarity metrics.
"""

from typing import Tuple, List
import difflib


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein (edit) distance between two strings.
    
    Args:
        s1: First string
        s2: Second string
        
    Returns:
        Edit distance (minimum number of operations to transform s1 to s2)
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = previous_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def similarity_ratio(s1: str, s2: str) -> float:
    """
    Calculate string similarity ratio (0.0 to 1.0).
    Uses the longest common subsequence approach.
    
    Args:
        s1: First string
        s2: Second string
        
    Returns:
        Similarity ratio between 0 and 1
    """
    if not s1 or not s2:
        return 0.0
    
    min_len = min(len(s1), len(s2))
    max_len = max(len(s1), len(s2))
    
    # LCS with memoization
    dp = [[0] * (min_len + 1) for _ in range(min_len + 1)]
    
    for i in range(1, min_len + 1):
        for j in range(1, min_len + 1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    
    return dp[min_len][min_len] / max_len


def tokenize_string(s: str) -> List[str]:
    """
    Tokenize a string into words.
    
    Args:
        s: Input string
        
    Returns:
        Lowercase list of tokens (words)
    """
    import re
    return re.findall(r'\b[a-z0-9]+\b', s.lower())


def fuzzy_search(
    items: List[Tuple[str, str]],  # list of (ticker, name) tuples
    query: str,
    min_score: float = 5.0,
    limit: int = 10
) -> List[Tuple[int, float]]:
    """
    Fuzzy search through a list of items.
    
    Args:
        items: List of (ticker, name) tuples
        query: Search query string
        min_score: Minimum score threshold
        limit: Maximum results to return
        
    Returns:
        List of (index, score) tuples sorted by score descending
    """
    scored = []
    query_tokens = tokenize_string(query)
    query_lower = query.lower()
    
    for i, (ticker, name) in enumerate(items):
        ticker_lower = ticker.lower()
        name_lower = name.lower()
        
        # Combine multiple scoring methods
        scores = []
        
        # 1. Ticker prefix match (high weight)
        if ticker_lower.startswith(query_lower):
            scores.append(10.0)
        elif query_lower in ticker_lower:
            scores.append(8.0)
        else:
            scores.append(fuzzy_match_score(ticker, name, query))
        
        # 2. Name partial match
        if name_lower.startswith(query_lower):
            scores.append(9.0)
        elif query_lower in name_lower:
            scores.append(7.0)
        else:
            token_match = sum(
                1 for q_token in query_tokens
                if any(q_token in tok for tok in tokenize_string(name))
            )
            scores.append(token_match * (4.0 / max(len(query_tokens), 1)))
        
        # Average score with weight to ticker match
        avg_score = sum(scores) / len(scores)
        scored.append((i, round(avg_score, 2)))
    
    # Sort by score descending, then by name length (shorter names rank higher for ties)
    scored.sort(key=lambda x: (-x[1], len(items[x[0]].name)))
    
    return scored[:limit]


def load_stocks_from_csv(csv_data: str) -> List[Tuple[str, str]]:
    """
    Parse stock data from CSV string.
    
    Args:
        csv_data: Raw CSV content
        
    Returns:
        List of (ticker, name) tuples
    """
    lines = csv_data.strip().split('\n')
    header = [h.lower() for h in lines[0].split(',')]
    
    ticker_idx = header.index('symbol') if 'symbol' in header else 0
    name_idx = header.index('name') if 'name' in header else 1
    
    stocks = []
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(',')]
        ticker = parts[ticker_idx].upper()
        name = parts[name_idx] if len(parts) > name_idx else ""
        stocks.append((ticker, name))
    
    return stocks

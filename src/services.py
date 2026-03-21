import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.models import GameRecommendRequest, UserRecommendRequest


def _parse_pg_array(val):
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [x for x in val.strip('{}').split(',') if x]


def _row_to_recommendation(row) -> dict:
    return {
        "game_id": row.game_id,
        "title": row.title,
        "url": row.url,
        "description": row.description,
        "header_image": row.header_image,
        "developer": row.developer,
        "publisher": row.publisher,
        "release_date": row.release_date,
        "release_date_original": row.release_date_original,
        "sim_score": row.sim_score,
        "total_review_count": row.total_review_count,
        "all_reviews": row.all_reviews,
        "total_review_positive_percent": row.total_review_positive_percent,
        "recent_review_count": row.recent_review_count,
        "recent_reviews": row.recent_reviews,
        "recent_review_positive_percent": row.recent_review_positive_percent,
        "genres": _parse_pg_array(row.genres),
        "tags": _parse_pg_array(row.tags),
    }


def get_item_recommendations(db: Session, request: GameRecommendRequest, limit: int = 20):
    """
    특정 게임 기준 유사도 검색
    """

    check_query = text("SELECT 1 FROM game_embeddings WHERE game_id = :g_id")
    if not db.execute(check_query, {"g_id": request.game_id}).fetchone():
        return None

    query = text("""
        WITH target AS (
            SELECT embedding FROM game_embeddings WHERE game_id = :g_id
        )
        SELECT
            b.game_id,
            b.title,
            b.url,
            b.description,
            b.header_image,
            b.developer,
            b.publisher,
            b.release_date,
            b.release_date_original,
            (1 - (e.embedding <=> (SELECT embedding FROM target))) AS sim_score,
            r.total_review_count,
            r.all_reviews,
            r.total_review_positive_percent,
            r.recent_review_count,
            r.recent_reviews,
            r.recent_review_positive_percent,
            COALESCE(g.genre_list, ARRAY[]::text[]) AS genres,
            COALESCE(t.tag_list, ARRAY[]::text[]) AS tags
        FROM game_embeddings e
        JOIN basic_info b ON e.game_id = b.game_id
        JOIN reviews r ON e.game_id = r.game_id
        LEFT JOIN (
            SELECT game_id, array_agg(genre_name) AS genre_list
            FROM genres GROUP BY game_id
        ) g ON b.game_id = g.game_id
        LEFT JOIN (
            SELECT game_id, array_agg(tag_name) AS tag_list
            FROM tags GROUP BY game_id
        ) t ON b.game_id = t.game_id
        WHERE e.game_id != :g_id
          AND b.release_date >= :release_date
          AND COALESCE(r.total_review_count, 0) >= :total_review_count
          AND COALESCE(r.total_review_positive_percent, 0) >= :total_review_positive_percent
          AND COALESCE(r.recent_review_count, 0) >= :recent_review_count
          AND COALESCE(r.recent_review_positive_percent, 0) >= :recent_review_positive_percent
        ORDER BY e.embedding <=> (SELECT embedding FROM target)
        LIMIT :limit
    """)
    
    results = db.execute(query, {
        "g_id": request.game_id,
        "release_date": request.release_date,
        "total_review_count": request.total_review_count,
        "total_review_positive_percent": request.total_review_positive_percent,
        "recent_review_count": request.recent_review_count,
        "recent_review_positive_percent": request.recent_review_positive_percent,
        "limit": limit
    }).fetchall()
    
    return [_row_to_recommendation(row) for row in results]

def get_user_recommendations(db: Session, request: UserRecommendRequest, limit: int = 20):
    """
    유저 플레이 정보 기반 유사도 검색
    """
    
    # 1. 유저 프로필 벡터 생성 과정
    user_games = request.games
    app_ids = [game.appid for game in user_games]
    
    # 예외 처리: 데이터가 비어있는 경우
    if not app_ids:
        return {"recommendations": [], "skipped_game_ids": []}

    # 보유 게임들의 임베딩 가져오기
    # app_ids 튜플 변환
    games_tuple = tuple(app_ids)
    
    # DB에서 embedding 조회 (형식 변환 주의)
    # pgvector 타입은 string으로 조회될 수 있어, 배열로 캐스팅하거나 후처리
    get_vectors_query = text(f"""
        SELECT game_id, embedding::text
        FROM game_embeddings 
        WHERE game_id IN :app_ids
    """)
    
    # In clause 파라미터 바인딩을 위해 tuple 사용
    vectors_results = db.execute(get_vectors_query, {"app_ids": games_tuple}).fetchall()
    
    if not vectors_results:
        return {"recommendations": [], "skipped_game_ids": app_ids}

    vector_map = {}
    import json
    for row in vectors_results:
        # pgvector 반환 텍스트가 [1,2,3] 형태이므로 json.loads 또는 eval 가능
        vec_str = row.embedding
        if vec_str.startswith('[') and vec_str.endswith(']'):
            try:
                vector_map[row.game_id] = np.array(json.loads(vec_str), dtype=float)
            except Exception:
                pass

    if not vector_map:
        return {"recommendations": [], "skipped_game_ids": app_ids}
    
    # 벡터 차원수 파악 (보통 446 또는 가변 모델)
    sample_vec_size = len(list(vector_map.values())[0])
    combined_user_vector = np.zeros(sample_vec_size, dtype=float)
    
    for user_game in user_games:
        game_id = user_game.appid
        if game_id in vector_map:
            playtime = user_game.playtime_forever
            playtime_weight = np.log1p(playtime)  # log(1 + playtime)
            
            weighted_vector = vector_map[game_id] * playtime_weight
            combined_user_vector += weighted_vector

    # 정규화 (선택적 요소이지만, 코사인 유사도 서치 시 L2 Normalize 하는 것이 유리)
    norm = np.linalg.norm(combined_user_vector)
    if norm > 0:
        combined_user_vector = combined_user_vector / norm
        
    # 벡터를 다시 문자열 포맷으로 변환 ('[val1, val2, ...]')
    user_vector_str = f"[{','.join(map(str, combined_user_vector))}]"

    # 2. 결과 쿼리 수행
    search_query = text("""
        SELECT
            b.game_id,
            b.title,
            b.url,
            b.description,
            b.header_image,
            b.developer,
            b.publisher,
            b.release_date,
            b.release_date_original,
            (1 - (e.embedding <=> :user_vector)) AS sim_score,
            r.total_review_count,
            r.all_reviews,
            r.total_review_positive_percent,
            r.recent_review_count,
            r.recent_reviews,
            r.recent_review_positive_percent,
            COALESCE(g.genre_list, ARRAY[]::text[]) AS genres,
            COALESCE(t.tag_list, ARRAY[]::text[]) AS tags
        FROM game_embeddings e
        JOIN basic_info b ON e.game_id = b.game_id
        JOIN reviews r ON e.game_id = r.game_id
        LEFT JOIN (
            SELECT game_id, array_agg(genre_name) AS genre_list
            FROM genres GROUP BY game_id
        ) g ON b.game_id = g.game_id
        LEFT JOIN (
            SELECT game_id, array_agg(tag_name) AS tag_list
            FROM tags GROUP BY game_id
        ) t ON b.game_id = t.game_id
        WHERE e.game_id NOT IN :app_ids
          AND b.release_date >= :release_date
          AND COALESCE(r.total_review_count, 0) >= :total_review_count
          AND COALESCE(r.total_review_positive_percent, 0) >= :total_review_positive_percent
          AND COALESCE(r.recent_review_count, 0) >= :recent_review_count
          AND COALESCE(r.recent_review_positive_percent, 0) >= :recent_review_positive_percent
        ORDER BY e.embedding <=> :user_vector
        LIMIT :limit
    """)
    
    results = db.execute(search_query, {
        "user_vector": user_vector_str,
        "app_ids": games_tuple,
        "release_date": request.release_date,
        "total_review_count": request.total_review_count,
        "total_review_positive_percent": request.total_review_positive_percent,
        "recent_review_count": request.recent_review_count,
        "recent_review_positive_percent": request.recent_review_positive_percent,
        "limit": limit
    }).fetchall()

    embedded_ids = set(vector_map.keys())
    skipped_ids = [gid for gid in app_ids if gid not in embedded_ids]

    return {
        "recommendations": [_row_to_recommendation(row) for row in results],
        "skipped_game_ids": skipped_ids
    }

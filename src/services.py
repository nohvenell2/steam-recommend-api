import json
from collections import defaultdict

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.models import GameRecommendRequest, UserRecommendRequest


def _fetch_game_details(db: Session, game_ids_with_scores: list[tuple[int, float]]) -> list[dict]:
    """
    벡터 검색 결과(game_id + sim_score)를 받아 게임 전체 정보를 조회하여 반환.
    순서는 sim_score 내림차순(벡터 검색 결과 순서) 유지.
    """
    if not game_ids_with_scores:
        return []

    score_map = {game_id: score for game_id, score in game_ids_with_scores}
    game_ids = tuple(score_map.keys())

    # basic_info + reviews 조회
    info_query = text("""
        SELECT b.game_id, b.url, b.title, b.description, b.header_image,
               b.developer, b.publisher, b.release_date, b.release_date_original,
               r.total_review_count, r.all_reviews, r.total_review_positive_percent,
               r.recent_review_count, r.recent_reviews, r.recent_review_positive_percent
        FROM basic_info b
        LEFT JOIN reviews r ON b.game_id = r.game_id
        WHERE b.game_id IN :game_ids
    """)
    info_rows = db.execute(info_query, {"game_ids": game_ids}).fetchall()

    # genres 조회
    genres_query = text("SELECT game_id, genre_name FROM genres WHERE game_id IN :game_ids")
    genres_rows = db.execute(genres_query, {"game_ids": game_ids}).fetchall()
    genres_map = defaultdict(list)
    for row in genres_rows:
        genres_map[row.game_id].append(row.genre_name)

    # tags 조회
    tags_query = text("SELECT game_id, tag_name FROM tags WHERE game_id IN :game_ids")
    tags_rows = db.execute(tags_query, {"game_ids": game_ids}).fetchall()
    tags_map = defaultdict(list)
    for row in tags_rows:
        tags_map[row.game_id].append(row.tag_name)

    # 결과 조합 후 sim_score 기준 정렬 (벡터 검색 순서 유지)
    results = []
    for row in info_rows:
        results.append({
            "sim_score": score_map[row.game_id],
            "game_id": row.game_id,
            "url": row.url,
            "title": row.title,
            "description": row.description,
            "header_image": row.header_image,
            "developer": row.developer,
            "publisher": row.publisher,
            "release_date": row.release_date,
            "release_date_original": row.release_date_original,
            "total_review_count": row.total_review_count,
            "all_reviews": row.all_reviews,
            "total_review_positive_percent": row.total_review_positive_percent,
            "recent_review_count": row.recent_review_count,
            "recent_reviews": row.recent_reviews,
            "recent_review_positive_percent": row.recent_review_positive_percent,
            "genres": genres_map[row.game_id],
            "tags": tags_map[row.game_id],
        })

    results.sort(key=lambda x: x["sim_score"], reverse=True)
    return results


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
            e.game_id,
            (1 - (e.embedding <=> (SELECT embedding FROM target))) AS sim_score
        FROM game_embeddings e
        JOIN basic_info b ON e.game_id = b.game_id
        JOIN reviews r ON e.game_id = r.game_id
        WHERE e.game_id != :g_id
          AND b.release_date >= :release_date
          AND COALESCE(r.total_review_count, 0) >= :total_review_count
          AND COALESCE(r.total_review_positive_percent, 0) >= :total_review_positive_percent
          AND COALESCE(r.recent_review_count, 0) >= :recent_review_count
          AND COALESCE(r.recent_review_positive_percent, 0) >= :recent_review_positive_percent
        ORDER BY e.embedding <=> (SELECT embedding FROM target)
        LIMIT :limit
    """)

    rows = db.execute(query, {
        "g_id": request.game_id,
        "release_date": request.release_date,
        "total_review_count": request.total_review_count,
        "total_review_positive_percent": request.total_review_positive_percent,
        "recent_review_count": request.recent_review_count,
        "recent_review_positive_percent": request.recent_review_positive_percent,
        "limit": limit
    }).fetchall()

    return _fetch_game_details(db, [(row.game_id, row.sim_score) for row in rows])


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
    games_tuple = tuple(app_ids)

    # DB에서 embedding 조회 (형식 변환 주의)
    get_vectors_query = text("""
        SELECT game_id, embedding::text
        FROM game_embeddings
        WHERE game_id IN :app_ids
    """)

    vectors_results = db.execute(get_vectors_query, {"app_ids": games_tuple}).fetchall()

    if not vectors_results:
        return {"recommendations": [], "skipped_game_ids": app_ids}

    vector_map = {}
    for row in vectors_results:
        vec_str = row.embedding
        if vec_str.startswith('[') and vec_str.endswith(']'):
            try:
                vector_map[row.game_id] = np.array(json.loads(vec_str), dtype=float)
            except Exception:
                pass

    if not vector_map:
        return {"recommendations": [], "skipped_game_ids": app_ids}

    # 벡터 차원수 파악
    sample_vec_size = len(list(vector_map.values())[0])
    combined_user_vector = np.zeros(sample_vec_size, dtype=float)

    for user_game in user_games:
        game_id = user_game.appid
        if game_id in vector_map:
            playtime_weight = np.log1p(user_game.playtime_forever)  # log(1 + playtime)
            combined_user_vector += vector_map[game_id] * playtime_weight

    # 정규화 (코사인 유사도 서치 시 L2 Normalize)
    norm = np.linalg.norm(combined_user_vector)
    if norm > 0:
        combined_user_vector = combined_user_vector / norm

    user_vector_str = f"[{','.join(map(str, combined_user_vector))}]"

    # 2. 결과 쿼리 수행
    search_query = text("""
        SELECT
            e.game_id,
            (1 - (e.embedding <=> :user_vector)) AS sim_score
        FROM game_embeddings e
        JOIN basic_info b ON e.game_id = b.game_id
        JOIN reviews r ON e.game_id = r.game_id
        WHERE e.game_id NOT IN :app_ids
          AND b.release_date >= :release_date
          AND COALESCE(r.total_review_count, 0) >= :total_review_count
          AND COALESCE(r.total_review_positive_percent, 0) >= :total_review_positive_percent
          AND COALESCE(r.recent_review_count, 0) >= :recent_review_count
          AND COALESCE(r.recent_review_positive_percent, 0) >= :recent_review_positive_percent
        ORDER BY e.embedding <=> :user_vector
        LIMIT :limit
    """)

    rows = db.execute(search_query, {
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
        "recommendations": _fetch_game_details(db, [(row.game_id, row.sim_score) for row in rows]),
        "skipped_game_ids": skipped_ids
    }

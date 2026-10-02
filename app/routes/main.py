# app/routes/main.py - 메인 페이지 라우트 로직
"""
쇼핑몰 메인 페이지 및 기본 기능을 처리하는 라우트 모듈입니다.
Supabase에서 상품 데이터를 조회하여 템플릿에 전달합니다.
"""

import os
import re
import uuid
import random
import logging
from datetime import datetime, timezone
from flask import Blueprint, render_template, session, request, jsonify, redirect, url_for, flash
from app.supabase_client import get_supabase_client
from app.routes.auth import login_required, validate_password_policy, ERROR_MESSAGES

# 로깅 설정
logger = logging.getLogger(__name__)

# 메인 블루프린트 생성
main_bp = Blueprint('main', __name__)

# 카테고리 메타데이터 매핑
CATEGORY_TYPE_MAP = {
    1: {'name': '상의', 'code': 'top', 'badge_color': 'danger'},
    2: {'name': '바지', 'code': 'pants', 'badge_color': 'secondary'},
    3: {'name': '아우터', 'code': 'outer', 'badge_color': 'primary'},
    4: {'name': '원피스', 'code': 'dress', 'badge_color': 'info'},
    8: {'name': '치마', 'code': 'skirt', 'badge_color': 'warning'},
    5: {'name': '양말', 'code': 'socks', 'badge_color': 'success'}
}

# 신상품 슬러그 목록 (메인 추천 4개 + 카테고리별 신상품)
NEW_PRODUCT_SLUGS = [
    # 메인 대표 신상품 4개
    'basic-crop-tshirt',        # 상의 (category_id=1)
    'wide-denim-pants',         # 바지 (category_id=2)
    'overfit-cotton-jacket',    # 아우터 (category_id=3)
    'floral-midi-dress',        # 원피스 (category_id=4)
    # 바지 신상품 3개 (category_id=2)
    'new-wide-denim', 'new-pin-tuck-slacks', 'new-cargo-jogger-pants',
    # 원피스 신상품 4개 (category_id=4)
    'new-french-floral-dress', 'new-linen-shirt-dress', 'new-square-neck-mini-dress', 'new-slim-knit-dress',
    # 치마 신상품 4개 (category_id=8)
    'new-pleats-tennis-skirt', 'new-aline-denim-skirt', 'new-mermaid-slit-skirt', 'new-wrap-check-skirt',
    # 양말 신상품 2개 (category_id=5)
    'new-cotton-ribbed-socks-5pack', 'new-retro-stripe-crew-socks-3pack'
]


def _format_product(item: dict) -> dict:
    """
    Supabase 상품 원본 딕셔너리를 화면 표시용 포맷으로 가공하는 공통 함수
    """
    cat_info = CATEGORY_TYPE_MAP.get(
        item.get('category_id'),
        {'name': '기타', 'code': 'etc', 'badge_color': 'dark'}
    )

    price = float(item.get('price') or 0)
    sale_price = item.get('sale_price')

    if sale_price is not None and float(sale_price) < price:
        sale_num = int(float(sale_price))
        orig_num = int(price)
        discount_pct = int(round((1 - (sale_num / orig_num)) * 100))
        display_price = f"{sale_num:,}원"
        original_price_formatted = f"{orig_num:,}원"
        has_discount = True
    else:
        sale_num = int(price)
        discount_pct = 0
        display_price = f"{sale_num:,}원"
        original_price_formatted = None
        has_discount = False

    return {
        "id": item.get('id'),
        "name": item.get('name', '상품명 없음'),
        "slug": item.get('slug'),
        "category_name": cat_info.get('name', '기타'),
        "category_code": cat_info.get('code', 'etc'),
        "badge_color": cat_info.get('badge_color', 'dark'),
        "price": display_price,
        "original_price": original_price_formatted,
        "has_discount": has_discount,
        "discount_pct": discount_pct,
        "thumbnail_url": item.get('thumbnail_url') or "/static/images/products/crop-tshirt.jpg",
        "description": item.get('description', ''),
        "status": item.get('status', 'active'),
        "sale_price": item.get('sale_price'),
        "raw_price": item.get('price')
    }


def fetch_featured_products(limit: int = 4) -> list:
    """
    Supabase products 테이블에서 활성 및 추천 상품을 조회합니다.
    - 요구사항: is_active=true, is_featured=true 조건 적용
    - 테이블 스키마에 컬럼이 없을 경우(status 기반인 경우) 유연하게 대응
    - 실패 시 에러 로그를 출력하고 빈 리스트를 반환합니다.
    """
    try:
        supabase = get_supabase_client()

        # 1차 시도: is_active, is_featured 컬럼이 존재하는 경우
        try:
            response = (
                supabase.table('products')
                .select('*')
                .eq('is_active', True)
                .eq('is_featured', True)
                .limit(limit)
                .execute()
            )
            raw_products = response.data or []
        except Exception as column_err:
            # is_active 또는 is_featured 컬럼이 없는 스키마의 경우 status='active'로 fallback 조회
            logger.warning("is_active/is_featured 컬럼 조회 실패, status='active' 조건으로 대체 조회합니다: %s", column_err)
            response = (
                supabase.table('products')
                .select('*')
                .eq('status', 'active')
                .limit(limit)
                .execute()
            )
            raw_products = response.data or []

        # 데이터 가공: 가격 포맷팅 및 기본값 처리
        return [_format_product(item) for item in raw_products]

    except Exception as e:
        logger.error("Supabase 상품 조회 중 오류 발생: %s", e, exc_info=True)
        return []


@main_bp.route('/')
def index():
    """
    쇼핑몰 메인 홈 화면을 렌더링합니다.
    Supabase에서 조회한 상품 목록(products)을 템플릿에 전달합니다.
    """
    products = fetch_featured_products(limit=4)
    return render_template('index.html', products=products)


# ------------------------------------------------------------------------------
# 신상품(NEW ARRIVALS) 조회 로직 및 라우트
# 메인화면 추천 상품 4개(상의, 바지, 아우터, 원피스) + 카테고리별 신상품(바지, 원피스, 치마, 양말)
# ------------------------------------------------------------------------------
def fetch_new_arrivals() -> list:
    """
    Supabase products 테이블에서 신상품 목록을 조회하고 가공합니다.
    """
    raw_products = []
    try:
        supabase = get_supabase_client()
        res = (
            supabase.table('products')
            .select('*')
            .in_('slug', NEW_PRODUCT_SLUGS)
            .execute()
        )
        raw_products = res.data or []
    except Exception as e:
        logger.error("신상품 데이터 조회 실패: %s", e, exc_info=True)

    # slug 순서 유지용 매핑
    slug_order = {slug: i for i, slug in enumerate(NEW_PRODUCT_SLUGS)}
    raw_products.sort(key=lambda x: slug_order.get(x.get('slug', ''), 999))

    return [_format_product(item) for item in raw_products]


@main_bp.route('/new')
def new_arrivals():
    """
    신상품(NEW ARRIVALS) 전용 페이지 라우트
    카테고리 탭 필터(전체, 상의, 바지, 아우터, 원피스, 치마, 양말) 지원
    """
    current_category = request.args.get('category', 'all').lower()
    all_products = fetch_new_arrivals()

    valid_categories = ['top', 'pants', 'outer', 'dress', 'skirt', 'socks']

    # 카테고리별 상품 개수 집계
    counts = {
        'all': len(all_products),
        'top': sum(1 for p in all_products if p.get('category_code') == 'top'),
        'pants': sum(1 for p in all_products if p.get('category_code') == 'pants'),
        'outer': sum(1 for p in all_products if p.get('category_code') == 'outer'),
        'dress': sum(1 for p in all_products if p.get('category_code') == 'dress'),
        'skirt': sum(1 for p in all_products if p.get('category_code') == 'skirt'),
        'socks': sum(1 for p in all_products if p.get('category_code') == 'socks')
    }

    # 카테고리 필터링
    if current_category != 'all' and current_category in valid_categories:
        filtered_products = [p for p in all_products if p.get('category_code') == current_category]
    else:
        current_category = 'all'
        filtered_products = all_products

    return render_template(
        'new_arrivals.html',
        products=filtered_products,
        current_category=current_category,
        counts=counts
    )


# ------------------------------------------------------------------------------
# 상품 검색 (SEARCH) 라우트
# ------------------------------------------------------------------------------
@main_bp.route('/search')
def search():
    """
    상품명 및 설명 키워드 검색 라우트
    """
    raw_query = request.args.get('q', '').strip()[:200]
    query = ''.join(
        character if character.isalnum() or character.isspace() or character == '-' else ' '
        for character in raw_query
    )
    query = ' '.join(query.split())[:100]
    formatted_products = []

    if query:
        try:
            supabase = get_supabase_client()
            # 상품명 또는 설명에서 검색 (ilike)
            response = (
                supabase.table('products')
                .select('*')
                .or_(f"name.ilike.%{query}%,description.ilike.%{query}%")
                .execute()
            )
            raw_products = response.data or []
            formatted_products = [_format_product(item) for item in raw_products]
        except Exception as e:
            logger.error("상품 검색 중 오류 발생: %s", e, exc_info=True)

    return render_template('search.html', products=formatted_products, query=query)


# ------------------------------------------------------------------------------
# 회원 혜택 (MEMBERSHIP BENEFITS) 라우트
# ------------------------------------------------------------------------------
GRADE_BENEFITS = [
    {
        'grade': 'BRONZE',
        'badge_class': 'text-bg-secondary',
        'condition': '신규 가입 또는 20만원 미만 구매',
        'discount_rate': '1%',
        'reward_rate': '1%',
        'shipping': '5만원 이상 무료배송',
        'coupons': ['신규 회원 15% 웰컴 쿠폰', '생일 축하 5,000원 쿠폰'],
        'description': 'VIBE FASHION에 가입하신 모든 고객님께 기본 제공되는 혜택입니다.'
    },
    {
        'grade': 'SILVER',
        'badge_class': 'text-bg-light border text-dark',
        'condition': '누적 실결제액 20만원 이상',
        'discount_rate': '3%',
        'reward_rate': '2%',
        'shipping': '월 1회 무료배송 쿠폰 지급',
        'coupons': ['매월 5% 상시 할인 쿠폰', '생일 축하 10,000원 쿠폰'],
        'description': '스타일을 찾아가는 고객님을 위한 업그레이드 혜택입니다.'
    },
    {
        'grade': 'GOLD',
        'badge_class': 'text-bg-warning text-dark',
        'condition': '누적 실결제액 50만원 이상',
        'discount_rate': '5%',
        'reward_rate': '3%',
        'shipping': '전 상품 상시 무료배송',
        'coupons': ['매월 10% 상시 할인 쿠폰', '생일 축하 20,000원 쿠폰', '신상품 7% 얼리버드 쿠폰'],
        'description': 'VIBE FASHION을 꾸준히 사랑해 주시는 우수 고객님을 위한 특별 혜택입니다.'
    },
    {
        'grade': 'VIP',
        'badge_class': 'text-bg-dark border border-warning',
        'condition': '누적 실결제액 100만원 이상',
        'discount_rate': '10%',
        'reward_rate': '5%',
        'shipping': '전 상품 무료배송 & 무료반품 1회',
        'coupons': ['매월 15% VIP 시크릿 쿠폰', '생일 축하 30,000원 상품권', '시즌 오프 우선 입장권'],
        'description': '최고의 감각을 지닌 VIBE FASHION 최상위 VIP 고객님만을 위한 프리미엄 혜택입니다.'
    }
]


@main_bp.route('/benefits')
def benefits():
    """
    회원 등급별 혜택 및 멤버십 소개 페이지 라우트
    로그인 사용자일 경우 현재 등급, 누적 결제금액, 다음 등급 달성까지 필요한 금액을 계산해 제공합니다.
    """
    user_info = None
    user_grade = 'BRONZE'
    total_spent = 0

    if session.get('user'):
        user = session['user']
        user_id = user.get('id')
        user_grade = user.get('grade', 'BRONZE')

        # Supabase profiles 테이블에서 최신 total_spent 및 grade 조회
        try:
            supabase = get_supabase_client()
            prof_res = (
                supabase.table('profiles')
                .select('name, grade, total_spent')
                .eq('id', user_id)
                .maybe_single()
                .execute()
            )
            if prof_res and prof_res.data:
                user_grade = prof_res.data.get('grade') or user_grade
                total_spent = float(prof_res.data.get('total_spent') or 0)
                # 세션 등급 동기화
                session['user']['grade'] = user_grade
                session.modified = True
        except Exception as e:
            logger.warning("회원 혜택 페이지 프로필 조회 실패: %s", e)

        # 다음 등급 및 필요 금액 계산
        # BRONZE (0~20만) -> SILVER (20만) -> GOLD (50만) -> VIP (100만)
        if total_spent < 200000:
            target_grade = 'SILVER'
            target_amount = 200000
        elif total_spent < 500000:
            target_grade = 'GOLD'
            target_amount = 500000
        elif total_spent < 1000000:
            target_grade = 'VIP'
            target_amount = 1000000
        else:
            target_grade = 'MAX'
            target_amount = 1000000

        needed_amount = max(0, target_amount - total_spent)
        progress_pct = min(100, int((total_spent / target_amount) * 100)) if target_amount > 0 else 100

        user_info = {
            'name': user.get('name', '고객'),
            'email': user.get('email', ''),
            'grade': user_grade,
            'total_spent': total_spent,
            'total_spent_formatted': f"{int(total_spent):,}원",
            'target_grade': target_grade,
            'needed_amount_formatted': f"{int(needed_amount):,}원",
            'progress_pct': progress_pct
        }

    return render_template(
        'benefits.html',
        grade_benefits=GRADE_BENEFITS,
        user_info=user_info
    )


# ------------------------------------------------------------------------------
# 상품 상세 (Product Detail) 헬퍼 함수
# ------------------------------------------------------------------------------
def _fetch_product_by_id(product_id: str) -> dict | None:
    """Supabase products 테이블에서 단일 상품 정보를 조회하고 포맷팅하여 반환합니다."""
    try:
        supabase = get_supabase_client()
        res = (
            supabase.table('products')
            .select('*')
            .eq('id', product_id)
            .maybe_single()
            .execute()
        )
        if res and res.data:
            return _format_product(res.data)
        return None
    except Exception as e:
        logger.error("상품 상세 조회 실패 (id: %s): %s", product_id, e, exc_info=True)
        return None


def _fetch_product_colors(product_id: str) -> list[str]:
    """product_options 테이블에서 해당 상품의 유효한 색상 목록을 중복 없이 정렬하여 반환합니다."""
    try:
        supabase = get_supabase_client()
        res = (
            supabase.table('product_options')
            .select('color')
            .eq('product_id', product_id)
            .not_.is_('color', 'null')
            .execute()
        )
        if res and res.data:
            return sorted(list({
                row['color'].strip()
                for row in res.data
                if row.get('color') and row['color'].strip()
            }))
        return []
    except Exception as e:
        logger.warning("상품 옵션 색상 목록 조회 경고 (id: %s): %s", product_id, e)
        return []


def _fetch_sizes_by_color(product_id: str, color: str) -> list[dict]:
    """특정 상품 및 색상에 해당하는 사이즈와 재고 목록을 표준 순서로 정렬하여 반환합니다."""
    if not color:
        return []

    try:
        supabase = get_supabase_client()
        res = (
            supabase.table('product_options')
            .select('id, size, stock, stock_quantity')
            .eq('product_id', product_id)
            .eq('color', color)
            .not_.is_('size', 'null')
            .execute()
        )
        rows = res.data or []

        # 사이즈 정렬 기준 정의 (XS -> S -> M -> L -> XL -> FREE -> 기타)
        size_priority = {'XS': 1, 'S': 2, 'M': 3, 'L': 4, 'XL': 5, 'FREE': 6}

        def sort_key(item):
            s = str(item.get('size', '')).upper()
            return size_priority.get(s, 99), s

        sizes = []
        for r in rows:
            stock_val = r.get('stock')
            if stock_val is None:
                stock_val = r.get('stock_quantity', 0)
            sizes.append({
                'id': r.get('id'),
                'size': r.get('size'),
                'stock': int(stock_val or 0)
            })

        sizes.sort(key=sort_key)
        return sizes
    except Exception as e:
        logger.error("사이즈 옵션 조회 실패 (product_id: %s, color: %s): %s", product_id, color, e)
        return []


# ------------------------------------------------------------------------------
# 상품 상세 (Product Detail) 라우트 및 옵션 API
# ------------------------------------------------------------------------------
@main_bp.route('/products/<product_id>')
def product_detail(product_id: str):
    """
    상품 상세 페이지 렌더링 라우트
    - Supabase products 테이블에서 상품 정보 조회
    - product_options 테이블에서 유효 색상 목록 조회
    - 상품 정보와 색상 목록을 템플릿에 전달
    """
    product = _fetch_product_by_id(product_id)
    if not product:
        flash('존재하지 않거나 삭제된 상품입니다.', 'warning')
        return redirect(url_for('main.index'))

    colors = _fetch_product_colors(product_id)
    return render_template('product_detail.html', product=product, colors=colors)


@main_bp.route('/api/products/<product_id>/sizes', methods=['GET'])
@main_bp.route('/api/products/<product_id>/options', methods=['GET'])
def get_product_sizes(product_id: str):
    """
    특정 상품의 선택된 색상에 해당하는 사이즈 및 재고 목록을 반환하는 API
    - Query: ?color=<선택한 색상>
    - Response: JSON [ {"size": "S", "stock": 3}, {"size": "M", "stock": 0} ]
    """
    color = request.args.get('color', '').strip()
    sizes = _fetch_sizes_by_color(product_id, color)
    return jsonify(sizes)


@main_bp.route('/api/products/<product_id>/colors', methods=['GET'])
def get_product_colors(product_id: str):
    """
    특정 상품의 유효한 색상(color) 목록을 반환하는 API
    - Response: JSON { "colors": ["Black", "White", "Navy"] }
    """
    colors = _fetch_product_colors(product_id)
    return jsonify({"colors": colors})


# ------------------------------------------------------------------------------
# 위시리스트(관심 상품) 헬퍼 및 라우트
# ------------------------------------------------------------------------------
def _get_wishlist():
    """세션에서 위시리스트 리스트를 반환합니다. 구조: [product_id, ...]"""
    if 'wishlist' not in session:
        session['wishlist'] = []
    return session['wishlist']


@main_bp.route('/wishlist')
def wishlist_view():
    """
    관심 상품 페이지 렌더링 라우트
    로그인하지 않은 경우 로그인 페이지로 리다이렉트 (플래시 안내)
    """
    if not session.get('user'):
        flash('로그인해야 이용 가능한 페이지입니다.', 'warning')
        return redirect(url_for('auth.login'))

    wishlist_ids = _get_wishlist()
    products = []

    if wishlist_ids:
        try:
            supabase = get_supabase_client()
            response = supabase.table('products').select('*').in_('id', wishlist_ids).execute()
            raw_products = response.data or []
            products = [_format_product(item) for item in raw_products]
        except Exception as e:
            logger.error("위시리스트 상품 조회 실패: %s", e, exc_info=True)

    return render_template('wishlist.html', products=products)


@main_bp.route('/api/wishlist/toggle', methods=['POST'])
def toggle_wishlist_api():
    """
    관심 상품 토글 API (세션 기반)
    """
    if not session.get('user'):
        return jsonify({"success": False, "message": "로그인해야 이용 가능한 기능입니다.", "need_login": True}), 401

    data = request.get_json(silent=True) or {}
    product_id = data.get('product_id')

    if not product_id:
        return jsonify({"success": False, "message": "상품 아이디가 필요합니다."}), 400

    wishlist = _get_wishlist()
    if product_id in wishlist:
        wishlist.remove(product_id)
        is_added = False
    else:
        wishlist.append(product_id)
        is_added = True

    session.modified = True
    return jsonify({
        "success": True,
        "is_added": is_added,
        "wishlist_count": len(wishlist)
    })


# ------------------------------------------------------------------------------
# 장바구니 헬퍼 및 세션 관리 함수
# ------------------------------------------------------------------------------
def _get_cart():
    """세션에서 장바구니 딕셔너리를 반환합니다. 구조: {product_id: quantity}"""
    if 'cart' not in session:
        session['cart'] = {}
    return session['cart']


def _get_cart_count(cart):
    """장바구니 전체 상품 수량을 계산합니다."""
    return sum(cart.values())


def _fetch_cart_items_for_user(user_id: str) -> dict:
    """
    로그인 사용자의 DB 장바구니 아이템 및 금액 요약을 조회합니다.
    """
    cart_items = []
    total_goods_price = 0
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    db_client = get_supabase_client(use_service_role=bool(service_key))

    if user_id:
        try:
            res = (
                db_client.table('carts')
                .select('id, quantity, product_id, option_id, product_options(*), products(*)')
                .eq('user_id', user_id)
                .order('created_at', desc=True)
                .execute()
            )
            rows = res.data or []

            # 세션 동기화
            session_cart = _get_cart()
            session_cart.clear()

            for row in rows:
                product = row.get('products') or {}
                option = row.get('product_options') or {}
                qty = int(row.get('quantity', 1))
                pid = row.get('product_id')
                cid = row.get('id')
                opt_id = row.get('option_id')

                session_cart[pid] = session_cart.get(pid, 0) + qty

                unit_price = int(float(product.get('sale_price') if product.get('sale_price') is not None else product.get('price', 0)))
                add_price = int(float(option.get('additional_price') or 0))
                unit_price += add_price
                subtotal = unit_price * qty
                total_goods_price += subtotal

                color = option.get('color')
                size = option.get('size')
                if not color and not size and option.get('option_name'):
                    parts = option.get('option_name', '').split('/')
                    if len(parts) == 2:
                        color = parts[0].strip()
                        size = parts[1].strip()

                raw_stock = option.get('stock') if option.get('stock') is not None else option.get('stock_quantity', 0)
                try:
                    stock = int(raw_stock)
                except (ValueError, TypeError):
                    stock = 0

                cart_items.append({
                    "id": cid,
                    "cart_id": cid,
                    "product_id": pid,
                    "option_id": opt_id,
                    "name": product.get('name', '상품명 없음'),
                    "color": color,
                    "size": size,
                    "stock": stock,
                    "unit_price": unit_price,
                    "unit_price_formatted": f"{unit_price:,}원",
                    "quantity": qty,
                    "subtotal": subtotal,
                    "subtotal_formatted": f"{subtotal:,}원",
                    "thumbnail_url": product.get('thumbnail_url') or "/static/images/products/crop-tshirt.jpg",
                    "description": product.get('description', '')
                })

            session.modified = True

        except Exception as e:
            logger.error("DB 장바구니 조회 실패 (user_id: %s): %s", user_id, e, exc_info=True)

    # 배송비 정책: 50,000원 이상 구매 시 무료 배송 (미만 시 3,000원)
    shipping_fee = 0 if (total_goods_price >= 50000 or total_goods_price == 0) else 3000
    final_payment_amount = total_goods_price + shipping_fee

    # 품절 상품(stock <= 0) 포함 여부 확인
    has_out_of_stock = any(item.get('stock', 0) <= 0 for item in cart_items)

    return {
        "cart_items": cart_items,
        "total_goods_price": total_goods_price,
        "total_goods_price_formatted": f"{total_goods_price:,}원",
        "shipping_fee": shipping_fee,
        "shipping_fee_formatted": f"{shipping_fee:,}원" if shipping_fee > 0 else "무료",
        "final_payment_amount": final_payment_amount,
        "final_payment_amount_formatted": f"{final_payment_amount:,}원",
        "has_out_of_stock": has_out_of_stock
    }


@main_bp.route('/cart')
def cart_view():
    """
    장바구니 페이지 렌더링 라우트
    - 로그인 사용자의 경우: Supabase carts 테이블(옵션 정보 포함)에서 조회
    - 비로그인 사용자의 경우: 세션 cart에서 조회
    """
    user_id = _get_current_user_id()
    supabase = get_supabase_client()

    # 1. 로그인 사용자의 DB 장바구니 우선 조회
    if user_id:
        data = _fetch_cart_items_for_user(user_id)
        return render_template(
            'cart.html',
            cart_items=data['cart_items'],
            total_goods_price=data['total_goods_price'],
            total_goods_price_formatted=data['total_goods_price_formatted'],
            shipping_fee=data['shipping_fee'],
            shipping_fee_formatted=data['shipping_fee_formatted'],
            final_payment_amount=data['final_payment_amount'],
            final_payment_amount_formatted=data['final_payment_amount_formatted'],
            has_out_of_stock=data['has_out_of_stock']
        )

    # 2. 비로그인 사용자의 경우 세션 조회
    cart_items = []
    total_goods_price = 0
    cart = _get_cart()
    if cart:
        product_ids = list(cart.keys())
        try:
            response = supabase.table('products').select('*').in_('id', product_ids).execute()
            products_data = {p['id']: p for p in (response.data or [])}

            for pid, qty in cart.items():
                product = products_data.get(pid)
                if not product:
                    continue

                unit_price = int(float(product.get('sale_price') if product.get('sale_price') is not None else product.get('price', 0)))
                subtotal = unit_price * qty
                total_goods_price += subtotal

                cart_items.append({
                    "id": pid,
                    "cart_id": None,
                    "product_id": pid,
                    "option_id": None,
                    "name": product.get('name', '상품명 없음'),
                    "color": None,
                    "size": None,
                    "stock": 99,
                    "unit_price": unit_price,
                    "unit_price_formatted": f"{unit_price:,}원",
                    "quantity": qty,
                    "subtotal": subtotal,
                    "subtotal_formatted": f"{subtotal:,}원",
                    "thumbnail_url": product.get('thumbnail_url') or "/static/images/products/crop-tshirt.jpg",
                    "description": product.get('description', '')
                })
        except Exception as e:
            logger.error("세션 장바구니 상품 조회 실패: %s", e, exc_info=True)

    # 배송비 정책: 50,000원 이상 구매 시 무료 배송 (미만 시 3,000원)
    shipping_fee = 0 if (total_goods_price >= 50000 or total_goods_price == 0) else 3000
    final_payment_amount = total_goods_price + shipping_fee
    has_out_of_stock = any(item.get('stock', 0) <= 0 for item in cart_items)

    return render_template(
        'cart.html',
        cart_items=cart_items,
        total_goods_price=total_goods_price,
        total_goods_price_formatted=f"{total_goods_price:,}원",
        shipping_fee=shipping_fee,
        shipping_fee_formatted=f"{shipping_fee:,}원" if shipping_fee > 0 else "무료",
        final_payment_amount=final_payment_amount,
        final_payment_amount_formatted=f"{final_payment_amount:,}원",
        has_out_of_stock=has_out_of_stock
    )


@main_bp.route('/order/checkout', methods=['GET', 'POST'])
@login_required
def order_checkout():
    """
    주문서 작성/결제 페이지 라우트
    - GET: 로그인 필수, 장바구니/품절 검증 후 주문서 페이지 렌더링
    - POST: /order/create 로 위임하여 일관된 주문 처리
    """
    if request.method == 'POST':
        return order_create()

    user_id = _get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.login', next=request.url))

    cart_data = _fetch_cart_items_for_user(user_id)
    cart_items = cart_data['cart_items']

    # 1. 장바구니 비어있으면 /cart 리다이렉트
    if not cart_items:
        flash('장바구니가 비어 있어 주문할 수 없습니다.', 'warning')
        return redirect(url_for('main.cart_view'))

    # 2. 품절 상품이 하나라도 있으면 /cart 리다이렉트 및 안내
    if cart_data['has_out_of_stock']:
        flash('품절된 상품이 있어 주문할 수 없습니다.', 'danger')
        return redirect(url_for('main.cart_view'))

    profile = _fetch_user_profile(user_id)

    return render_template(
        'checkout.html',
        cart_items=cart_items,
        total_goods_price=cart_data['total_goods_price'],
        total_goods_price_formatted=cart_data['total_goods_price_formatted'],
        shipping_fee=cart_data['shipping_fee'],
        shipping_fee_formatted=cart_data['shipping_fee_formatted'],
        final_payment_amount=cart_data['final_payment_amount'],
        final_payment_amount_formatted=cart_data['final_payment_amount_formatted'],
        profile=profile,
        form_data={}
    )


@main_bp.route('/order/create', methods=['POST'])
@login_required
def order_create():
    """
    주문 생성 처리 라우트 (POST /order/create)
    처리 순서:
    1. 장바구니 조회 + 재고 확인 (재고 부족 시 에러, 처리 중단, 아무 것도 쓰지 않음)
    2. 배송지 입력값 서버 측 재검증 (수령인, 휴대폰 번호 패턴, 주소 최소 길이)
    3. 주문번호 생성: 'VF-' + 오늘날짜(YYYYMMDD) + '-' + 4자리 랜덤숫자 + 밀리초 타임스탬프 뒷 3자리
    4. orders 테이블에 INSERT (status='paid', paid_at=now())
    5. order_items INSERT (상품명, 색상, 사이즈, 가격 스냅샷)
    6. product_options.stock_quantity 차감 (service_role 키 RLS 우회, 조건부 UPDATE)
       - 영향받은 행이 0개면 "방금 재고가 소진되었습니다" 에러로 롤백 처리
    7. carts 아이템 DELETE
    8. /order/complete/<order_id> 리다이렉트
    """
    user_id = _get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.login', next=request.url))

    profile = _fetch_user_profile(user_id)

    # 1. 장바구니 조회 + 재고 확인 (재고 부족 시 에러, 처리 중단, 아무 것도 쓰지 않음)
    cart_data = _fetch_cart_items_for_user(user_id)
    cart_items = cart_data['cart_items']

    if not cart_items:
        flash('장바구니가 비어 있어 주문할 수 없습니다.', 'warning')
        return redirect(url_for('main.cart_view'))

    # 각 장바구니 품목의 재고 유효성 검사
    for item in cart_items:
        curr_stock = item.get('stock', 0)
        req_qty = item.get('quantity', 1)
        if curr_stock < req_qty or curr_stock <= 0:
            flash(f"'{item.get('name')}' 상품의 재고가 부족합니다 (현재 재고: {curr_stock}개). 주문이 중단되었습니다.", 'danger')
            return redirect(url_for('main.cart_view'))

    if cart_data['has_out_of_stock']:
        flash('품절된 상품이 있어 주문할 수 없습니다.', 'danger')
        return redirect(url_for('main.cart_view'))

    # 2. 배송지 입력값 서버 측 재검증 (휴대폰 번호 패턴, 주소 최소 길이)
    recipient_name = request.form.get('recipient_name', '').strip()
    recipient_phone = request.form.get('recipient_phone', '').strip()
    shipping_postal_code = request.form.get('shipping_postal_code', '').strip()
    shipping_address = request.form.get('shipping_address', '').strip()
    shipping_address_detail = request.form.get('shipping_address_detail', '').strip()
    shipping_memo = request.form.get('shipping_memo', '').strip()

    if not recipient_name:
        flash('수령인 이름을 입력해 주세요.', 'danger')
        return render_template(
            'checkout.html',
            cart_items=cart_items,
            total_goods_price=cart_data['total_goods_price'],
            total_goods_price_formatted=cart_data['total_goods_price_formatted'],
            shipping_fee=cart_data['shipping_fee'],
            shipping_fee_formatted=cart_data['shipping_fee_formatted'],
            final_payment_amount=cart_data['final_payment_amount'],
            final_payment_amount_formatted=cart_data['final_payment_amount_formatted'],
            profile=profile,
            form_data=request.form
        )

    # 휴대폰 번호 패턴 검증 (010-0000-0000)
    phone_pattern = r'^010-\d{4}-\d{4}$'
    if not re.match(phone_pattern, recipient_phone):
        flash('휴대폰 번호는 010-0000-0000 형식으로 입력해 주세요.', 'danger')
        return render_template(
            'checkout.html',
            cart_items=cart_items,
            total_goods_price=cart_data['total_goods_price'],
            total_goods_price_formatted=cart_data['total_goods_price_formatted'],
            shipping_fee=cart_data['shipping_fee'],
            shipping_fee_formatted=cart_data['shipping_fee_formatted'],
            final_payment_amount=cart_data['final_payment_amount'],
            final_payment_amount_formatted=cart_data['final_payment_amount_formatted'],
            profile=profile,
            form_data=request.form
        )

    # 배송 주소 최소 5자 이상 검증
    if len(shipping_address) < 5:
        flash('배송 주소는 최소 5자 이상 입력해 주세요.', 'danger')
        return render_template(
            'checkout.html',
            cart_items=cart_items,
            total_goods_price=cart_data['total_goods_price'],
            total_goods_price_formatted=cart_data['total_goods_price_formatted'],
            shipping_fee=cart_data['shipping_fee'],
            shipping_fee_formatted=cart_data['shipping_fee_formatted'],
            final_payment_amount=cart_data['final_payment_amount'],
            final_payment_amount_formatted=cart_data['final_payment_amount_formatted'],
            profile=profile,
            form_data=request.form
        )

    # 3. 주문번호 생성: 'VF-' + 오늘날짜(YYYYMMDD) + '-' + 4자리 랜덤숫자 + 밀리초 타임스탬프 뒷 3자리
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime('%Y%m%d')
    rand_4digit = f"{random.randint(0, 9999):04d}"
    millis_suffix = f"{int(now_utc.timestamp() * 1000) % 1000:03d}"
    order_number = f"VF-{today_str}-{rand_4digit}{millis_suffix}"

    # Supabase service_role 클라이언트 획득 (RLS 우회 및 트랜잭션 성격의 처리)
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = get_supabase_client(use_service_role=bool(service_key))

    created_order_id = None
    deducted_options = []  # 롤백용: (opt_id, deducted_quantity)

    try:
        # 4. orders 테이블에 INSERT (status='paid', paid_at=now())
        order_payload = {
            'order_number': order_number,
            'user_id': user_id,
            'status': 'paid',
            'total_amount': cart_data['total_goods_price'],
            'discount_amount': 0,
            'shipping_fee': cart_data['shipping_fee'],
            'payment_amount': cart_data['final_payment_amount'],
            'payment_method': '신용카드(더미)',
            'payment_id': f"PAY-{uuid.uuid4().hex[:12].upper()}",
            'recipient_name': recipient_name,
            'recipient_phone': recipient_phone,
            'shipping_postal_code': shipping_postal_code or '',
            'shipping_address': shipping_address,
            'shipping_address_detail': shipping_address_detail or '',
            'shipping_memo': shipping_memo or '',
            'paid_at': now_utc.isoformat(),
        }

        order_res = supabase.table('orders').insert(order_payload).execute()
        if not order_res or not order_res.data:
            raise Exception("주문 정보 저장에 실패했습니다.")

        created_order = order_res.data[0]
        created_order_id = created_order['id']

        # 5. order_items INSERT (상품명, 색상, 사이즈, 가격 스냅샷)
        order_items_payload = []
        for item in cart_items:
            opt_parts = []
            if item.get('color'):
                opt_parts.append(str(item['color']))
            if item.get('size'):
                opt_parts.append(str(item['size']))
            opt_name = " / ".join(opt_parts) if opt_parts else None

            order_items_payload.append({
                'order_id': created_order_id,
                'product_id': item.get('product_id'),
                'option_id': item.get('option_id'),
                'product_name': item.get('name', '상품명 없음'),
                'option_name': opt_name,
                'unit_price': item.get('unit_price', 0),
                'quantity': item.get('quantity', 1),
                'total_price': item.get('subtotal', 0)
            })

        if order_items_payload:
            supabase.table('order_items').insert(order_items_payload).execute()

        # 6. product_options.stock_quantity 차감 — 반드시 조건부 UPDATE 사용:
        #    UPDATE ... SET stock = stock - 수량 WHERE id = 옵션ID AND stock >= 수량
        #    영향받은 행이 0개면 "방금 재고가 소진되었습니다" 에러로 롤백 처리
        for item in cart_items:
            opt_id = item.get('option_id')
            qty = item.get('quantity', 1)
            if not opt_id:
                continue

            # 현재 최신 재고 조회
            latest_opt_res = (
                supabase.table('product_options')
                .select('id, stock, stock_quantity')
                .eq('id', opt_id)
                .maybe_single()
                .execute()
            )
            if not latest_opt_res or not latest_opt_res.data:
                raise Exception(f"상품 옵션을 찾을 수 없습니다: {item.get('name')}")

            current_stock = latest_opt_res.data.get('stock')
            if current_stock is None:
                current_stock = latest_opt_res.data.get('stock_quantity', 0)
            current_stock = int(current_stock or 0)

            # 조건부 UPDATE (WHERE id = 옵션ID AND stock >= 수량)
            new_stock = current_stock - qty
            update_payload = {'stock_quantity': new_stock}
            if 'stock' in latest_opt_res.data:
                update_payload['stock'] = new_stock

            update_res = (
                supabase.table('product_options')
                .update(update_payload)
                .eq('id', opt_id)
                .gte('stock_quantity', qty)
                .execute()
            )

            if not update_res or not update_res.data or len(update_res.data) == 0:
                raise ValueError(f"방금 재고가 소진되었습니다. ({item.get('name')})")

            deducted_options.append((opt_id, qty, current_stock))

        # 7. carts 아이템 DELETE
        supabase.table('carts').delete().eq('user_id', user_id).execute()
        session_cart = _get_cart()
        session_cart.clear()
        session.modified = True

        # 8. /order/complete/<order_id> 리다이렉트
        flash('주문이 성공적으로 완료되었습니다.', 'success')
        return redirect(url_for('main.order_complete', order_id=created_order_id))

    except ValueError as ve:
        # 재고 소진 등의 비즈니스 검증 실패 -> 롤백 처리
        logger.warning("주문 생성 재고 부족/소진 롤백 발생: %s", ve)
        _rollback_order(supabase, created_order_id, deducted_options)
        flash(str(ve), 'danger')
        return redirect(url_for('main.cart_view'))

    except Exception as e:
        logger.error("주문 생성 중 오류 발생 및 롤백 실행: %s", e, exc_info=True)
        _rollback_order(supabase, created_order_id, deducted_options)
        flash('주문 처리 중 오류가 발생했습니다. 다시 시도해 주세요.', 'danger')
        return render_template(
            'checkout.html',
            cart_items=cart_items,
            total_goods_price=cart_data['total_goods_price'],
            total_goods_price_formatted=cart_data['total_goods_price_formatted'],
            shipping_fee=cart_data['shipping_fee'],
            shipping_fee_formatted=cart_data['shipping_fee_formatted'],
            final_payment_amount=cart_data['final_payment_amount'],
            final_payment_amount_formatted=cart_data['final_payment_amount_formatted'],
            profile=profile,
            form_data=request.form
        )


def _rollback_order(supabase, order_id: str | None, deducted_options: list):
    """
    주문 실패 시 orders 행 삭제 및 이미 차감된 옵션 재고 복구 (롤백 처리)
    """
    if not supabase:
        return

    # 1. 차감되었던 옵션 재고 원복
    for item in deducted_options:
        try:
            opt_id, qty, original_stock = item
            supabase.table('product_options').update({'stock_quantity': original_stock}).eq('id', opt_id).execute()
        except Exception as err:
            logger.error("재고 복구 롤백 실패 (opt_id: %s): %s", item[0], err)

    # 2. 생성된 order 삭제 (ON DELETE CASCADE로 order_items도 자동 삭제)
    if order_id:
        try:
            supabase.table('orders').delete().eq('id', order_id).execute()
        except Exception as err:
            logger.error("주문 레코드 삭제 롤백 실패 (order_id: %s): %s", order_id, err)


@main_bp.route('/order/complete/<order_id>')
@login_required
def order_complete(order_id: str):
    """
    주문 완료 결과 안내 페이지 라우트 (GET /order/complete/<order_id>)
    - 로그인 필수
    - 본인 주문 확인 (다른 사용자의 order_id 접근 차단)
    - 주문번호, 배송지, 주문 상품 목록, 결제 금액 표시
    """
    user_id = _get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.login'))

    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = get_supabase_client(use_service_role=bool(service_key))

    try:
        # order_id가 UUID 형식인지 또는 주문번호 형식인지 확인 후 조회
        is_uuid = bool(re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', order_id, re.IGNORECASE))
        query = supabase.table('orders').select('*')
        if is_uuid:
            order_res = query.eq('id', order_id).maybe_single().execute()
        else:
            order_res = query.eq('order_number', order_id).maybe_single().execute()

        if not order_res or not order_res.data:
            flash('주문 정보를 찾을 수 없습니다.', 'warning')
            return redirect(url_for('main.index'))

        order = order_res.data

        # 1. 본인 주문이 맞는지 확인 (다른 사용자의 order_id 접근 차단)
        if order.get('user_id') != user_id:
            logger.warning("타인의 주문 접근 차단 (user_id: %s, target_order_id: %s, owner_id: %s)", user_id, order_id, order.get('user_id'))
            flash('다른 사용자의 주문 정보에는 접근할 수 없습니다.', 'danger')
            return redirect(url_for('main.mypage'))

        # 2. 주문 상품 품목 조회 (order_items 및 상품 썸네일)
        items_res = (
            supabase.table('order_items')
            .select('*, products(thumbnail_url)')
            .eq('order_id', order['id'])
            .order('created_at', desc=False)
            .execute()
        )
        raw_items = items_res.data or []
        order_items = []
        for ri in raw_items:
            product = ri.get('products') or {}
            ri['thumbnail_url'] = product.get('thumbnail_url') or "/static/images/products/crop-tshirt.jpg"
            ri['unit_price_formatted'] = f"{int(float(ri.get('unit_price', 0))):,}원"
            ri['total_price_formatted'] = f"{int(float(ri.get('total_price', 0))):,}원"
            order_items.append(ri)

        # 3. 결제 금액 표시 포맷팅
        order_formatted = {
            **order,
            'total_amount_formatted': f"{int(float(order.get('total_amount', 0))):,}원",
            'shipping_fee_formatted': f"{int(float(order.get('shipping_fee', 0))):,}원" if float(order.get('shipping_fee', 0)) > 0 else "무료",
            'payment_amount_formatted': f"{int(float(order.get('payment_amount', 0))):,}원",
        }

        return render_template('order_complete.html', order=order_formatted, order_items=order_items)

    except Exception as e:
        logger.error("주문 완료 페이지 조회 오류: %s", e, exc_info=True)
        flash('주문 정보를 불러오는 중 오류가 발생했습니다.', 'danger')
        return redirect(url_for('main.index'))


@main_bp.route('/cart/add', methods=['POST'])
@main_bp.route('/api/cart/add', methods=['POST'])
def cart_add():
    """
    장바구니 담기 라우트 (/cart/add 및 /api/cart/add 통합)
    """
    data = request.get_json(silent=True) if request.is_json else request.form.to_dict()
    data = data or {}

    option_id = data.get('product_option_id') or data.get('option_id')
    product_id = data.get('product_id')

    try:
        quantity = int(data.get('quantity', 1))
    except (ValueError, TypeError):
        quantity = 0

    if quantity <= 0:
        return jsonify({"success": False, "message": "유효하지 않은 수량입니다."}), 400

    # A. 상품 옵션(색상/사이즈) 지정 담기
    if option_id:
        user_id = _get_current_user_id()
        if not user_id:
            if request.is_json:
                return jsonify({
                    "success": False,
                    "message": "로그인이 필요합니다.",
                    "redirect_url": url_for('auth.login', next=request.referrer or url_for('main.index'))
                }), 401
            return redirect(url_for('auth.login', next=request.url))

        service_key = os.getenv('SUPABASE_SERVICE_KEY')
        supabase = get_supabase_client(use_service_role=bool(service_key))
        try:
            # 옵션 및 현재 재고 조회
            opt_res = (
                supabase.table('product_options')
                .select('id, product_id, stock, stock_quantity')
                .eq('id', option_id)
                .maybe_single()
                .execute()
            )
            if not opt_res or not opt_res.data:
                return jsonify({"success": False, "message": "존재하지 않는 상품 옵션입니다."}), 404

            opt_data = opt_res.data
            resolved_product_id = opt_data.get('product_id') or product_id
            current_stock = opt_data.get('stock')
            if current_stock is None:
                current_stock = opt_data.get('stock_quantity', 0)
            current_stock = int(current_stock or 0)

            # 단일 요청 수량 재고 검증
            if quantity > current_stock:
                return jsonify({
                    "success": False,
                    "message": f"재고가 부족합니다(현재 {current_stock}개)"
                }), 400

            # 기존 장바구니 누적 확인
            cart_res = (
                supabase.table('carts')
                .select('id, quantity')
                .eq('user_id', user_id)
                .eq('product_id', resolved_product_id)
                .eq('option_id', option_id)
                .maybe_single()
                .execute()
            )

            existing_item = cart_res.data if cart_res else None
            if existing_item:
                new_qty = int(existing_item.get('quantity', 0)) + quantity
                if new_qty > current_stock:
                    return jsonify({
                        "success": False,
                        "message": f"재고가 부족합니다(현재 {current_stock}개)"
                    }), 400

                supabase.table('carts').update({'quantity': new_qty}).eq('id', existing_item['id']).execute()
            else:
                supabase.table('carts').insert({
                    'user_id': user_id,
                    'product_id': resolved_product_id,
                    'option_id': option_id,
                    'quantity': quantity
                }).execute()

            # 세션 동기화
            cart = _get_cart()
            cart[resolved_product_id] = cart.get(resolved_product_id, 0) + quantity
            session.modified = True

            return jsonify({
                "success": True,
                "message": "장바구니에 담겼습니다",
                "cart_count": _get_cart_count(cart)
            })

        except Exception as e:
            logger.error("장바구니 옵션 담기 실패 (option_id: %s): %s", option_id, e, exc_info=True)
            return jsonify({"success": False, "message": "장바구니 담기 중 오류가 발생했습니다."}), 500

    # B. 기본 상품 간편 담기 (옵션 미지정)
    if not product_id:
        return jsonify({"success": False, "message": "상품 아이디가 필요합니다."}), 400

    cart = _get_cart()
    cart[product_id] = cart.get(product_id, 0) + quantity
    session.modified = True

    return jsonify({
        "success": True,
        "message": "장바구니에 상품이 추가되었습니다.",
        "cart_count": _get_cart_count(cart)
    })


@main_bp.route('/api/cart/change-option', methods=['POST'])
def change_cart_option():
    """
    장바구니 항목의 옵션(색상/사이즈) 변경 API
    - Request: JSON { "cart_id": "...", "new_option_id": "..." }
    """
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({
            "success": False,
            "message": "로그인이 필요한 서비스입니다.",
            "redirect_url": url_for('auth.login', next=url_for('main.cart_view'))
        }), 401

    data = request.get_json(silent=True) or {}
    cart_id = data.get('cart_id')
    new_option_id = data.get('new_option_id')

    if not new_option_id or not cart_id:
        return jsonify({"success": False, "message": "필수 파라미터가 누락되었습니다."}), 400

    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = get_supabase_client(use_service_role=bool(service_key))
    try:
        # 1. 새 옵션의 재고 정보 조회
        opt_res = (
            supabase.table('product_options')
            .select('id, product_id, color, size, stock, stock_quantity')
            .eq('id', new_option_id)
            .maybe_single()
            .execute()
        )
        if not opt_res or not opt_res.data:
            return jsonify({"success": False, "message": "존재하지 않는 상품 옵션입니다."}), 404

        new_opt = opt_res.data
        new_stock = new_opt.get('stock')
        if new_stock is None:
            new_stock = new_opt.get('stock_quantity', 0)
        new_stock = int(new_stock or 0)

        # 2. 대상 장바구니 아이템 조회
        target_res = (
            supabase.table('carts')
            .select('*')
            .eq('user_id', user_id)
            .eq('id', cart_id)
            .maybe_single()
            .execute()
        )
        if not target_res or not target_res.data:
            return jsonify({"success": False, "message": "장바구니 아이템을 찾을 수 없습니다."}), 404

        target_item = target_res.data
        target_qty = int(target_item.get('quantity', 1))
        resolved_product_id = target_item['product_id']

        # 3. 재고 부족 검증 (현재 담긴 수량이 새 옵션의 재고보다 많은 경우)
        if target_qty > new_stock:
            return jsonify({
                "success": False,
                "message": f"선택한 옵션의 재고가 부족합니다 (현재 재고: {new_stock}개, 담긴 수량: {target_qty}개)"
            }), 400

        # 이미 동일한 옵션인 경우
        if target_item.get('option_id') == new_option_id:
            return jsonify({"success": True, "message": "이미 선택된 옵션과 동일합니다."})

        # 4. 동일한 새 옵션이 이미 장바구니에 존재하는지 확인
        existing_res = (
            supabase.table('carts')
            .select('*')
            .eq('user_id', user_id)
            .eq('product_id', resolved_product_id)
            .eq('option_id', new_option_id)
            .maybe_single()
            .execute()
        )
        existing_item = existing_res.data if existing_res else None

        if existing_item and existing_item['id'] != cart_id:
            combined_qty = int(existing_item.get('quantity', 0)) + target_qty
            if combined_qty > new_stock:
                return jsonify({
                    "success": False,
                    "message": f"장바구니에 이미 동일한 옵션이 담겨 있어 수량 합산 시 재고를 초과합니다 (합산: {combined_qty}개, 재고: {new_stock}개)"
                }), 400

            # 기존 레코드에 수량 합산 후 변경 전 레코드 삭제
            supabase.table('carts').update({'quantity': combined_qty}).eq('id', existing_item['id']).execute()
            supabase.table('carts').delete().eq('id', cart_id).execute()
        else:
            # 옵션 갱신
            supabase.table('carts').update({'option_id': new_option_id}).eq('id', cart_id).execute()

        return jsonify({
            "success": True,
            "message": "옵션이 성공적으로 변경되었습니다."
        })

    except Exception as e:
        logger.error("옵션 변경 실패 (cart_id: %s, new_opt: %s): %s", cart_id, new_option_id, e, exc_info=True)
        return jsonify({"success": False, "message": "옵션 변경 처리 중 오류가 발생했습니다."}), 500


@main_bp.route('/cart/<cart_id>', methods=['PATCH'])
def patch_cart_item(cart_id: str):
    """
    장바구니 수량 변경 라우트 (PATCH /cart/<cart_id>)
    - 요청 body: quantity (변경할 새 수량)
    - 로그인 확인 및 본인 소유 장바구니 아이템 검증 (타인 cart_id 차단)
    - quantity가 1 미만이면 400 에러
    - 변경하려는 quantity가 해당 옵션의 stock 초과 시 '재고가 부족합니다(현재 N개)' 에러, 변경하지 않음
    - 성공 시 DB UPDATE 후 새 소계(subtotal) 반환
    """
    # 1. 로그인 확인
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({
            "success": False,
            "message": "로그인이 필요한 서비스입니다.",
            "redirect_url": url_for('auth.login', next=url_for('main.cart_view'))
        }), 401

    # 2. 수량 파라미터 파싱 및 검증
    data = request.get_json(silent=True) or {}
    try:
        quantity = int(data.get('quantity'))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "올바른 수량을 입력해 주세요."}), 400

    if quantity < 1:
        return jsonify({"success": False, "message": "수량은 1개 이상이어야 합니다."}), 400

    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = get_supabase_client(use_service_role=bool(service_key))
    try:
        # 3. 본인 소유의 장바구니 아이템인지 확인 (타인 접근 차단)
        c_res = (
            supabase.table('carts')
            .select('id, user_id, product_id, option_id, quantity, product_options(*), products(*)')
            .eq('id', cart_id)
            .eq('user_id', user_id)
            .maybe_single()
            .execute()
        )

        if not c_res or not c_res.data:
            return jsonify({
                "success": False,
                "message": "장바구니 항목을 찾을 수 없거나 접근 권한이 없습니다."
            }), 404

        cart_item = c_res.data
        opt = cart_item.get('product_options') or {}
        product = cart_item.get('products') or {}

        # 4. 재고(stock) 확인 및 초과 여부 검증
        stock = opt.get('stock')
        if stock is None:
            stock = opt.get('stock_quantity', 0)
        stock = int(stock or 0)

        if quantity > stock:
            return jsonify({
                "success": False,
                "message": f"재고가 부족합니다(현재 {stock}개)"
            }), 400

        # 5. DB 수량 UPDATE
        supabase.table('carts').update({'quantity': quantity}).eq('id', cart_id).eq('user_id', user_id).execute()

        # 6. 새 소계(subtotal) 계산
        unit_price = int(float(product.get('sale_price') if product.get('sale_price') is not None else product.get('price', 0)))
        unit_price += int(float(opt.get('additional_price') or 0))
        subtotal = unit_price * quantity

        # 세션 카운트 동기화
        c_all = supabase.table('carts').select('product_id, quantity').eq('user_id', user_id).execute()
        cart = _get_cart()
        cart.clear()
        for r in (c_all.data or []):
            cart[r['product_id']] = cart.get(r['product_id'], 0) + int(r['quantity'])
        session.modified = True

        return jsonify({
            "success": True,
            "message": "수량이 변경되었습니다.",
            "quantity": quantity,
            "subtotal": subtotal,
            "subtotal_formatted": f"{subtotal:,}원",
            "cart_count": _get_cart_count(cart)
        })

    except Exception as e:
        logger.error("PATCH /cart/%s 수량 변경 실패: %s", cart_id, e, exc_info=True)
        return jsonify({"success": False, "message": "수량 변경 중 오류가 발생했습니다."}), 500


@main_bp.route('/cart/<cart_id>', methods=['DELETE'])
def delete_cart_item(cart_id: str):
    """
    장바구니 아이템 삭제 라우트 (DELETE /cart/<cart_id>)
    - 로그인 확인
    - 본인 소유의 장바구니 아이템인지 확인 후 삭제
    - 성공 시: {"success": true, "message": "상품이 장바구니에서 삭제되었습니다.", "cart_count": N}
    """
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({
            "success": False,
            "message": "로그인이 필요한 서비스입니다.",
            "redirect_url": url_for('auth.login', next=url_for('main.cart_view'))
        }), 401

    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = get_supabase_client(use_service_role=bool(service_key))

    try:
        # 1. 본인 소유의 장바구니 아이템인지 확인 (id 또는 product_id 대응)
        item_res = (
            supabase.table('carts')
            .select('id, user_id, product_id, quantity')
            .eq('id', cart_id)
            .eq('user_id', user_id)
            .maybe_single()
            .execute()
        )

        if not item_res or not item_res.data:
            item_res = (
                supabase.table('carts')
                .select('id, user_id, product_id, quantity')
                .eq('product_id', cart_id)
                .eq('user_id', user_id)
                .maybe_single()
                .execute()
            )

        if not item_res or not item_res.data:
            # 혹시 세션에만 있는 경우 세션에서 삭제
            cart = _get_cart()
            if cart_id in cart:
                cart.pop(cart_id, None)
                session.modified = True
                return jsonify({
                    "success": True,
                    "message": "상품이 장바구니에서 삭제되었습니다.",
                    "cart_count": _get_cart_count(cart)
                })
            return jsonify({
                "success": False,
                "message": "장바구니 항목을 찾을 수 없거나 삭제 권한이 없습니다."
            }), 404

        actual_id = item_res.data['id']
        # 2. 본인 아이템 확인 완료 후 삭제
        supabase.table('carts').delete().eq('id', actual_id).eq('user_id', user_id).execute()

        # 3. 세션 장바구니 수량 동기화
        c_all = supabase.table('carts').select('product_id, quantity').eq('user_id', user_id).execute()
        cart = _get_cart()
        cart.clear()
        for r in (c_all.data or []):
            cart[r['product_id']] = cart.get(r['product_id'], 0) + int(r['quantity'])
        session.modified = True

        total_count = _get_cart_count(cart)
        return jsonify({
            "success": True,
            "message": "상품이 장바구니에서 삭제되었습니다.",
            "cart_count": total_count
        })

    except Exception as e:
        logger.error("DELETE /cart/%s 삭제 실패: %s", cart_id, e, exc_info=True)
        return jsonify({"success": False, "message": "장바구니 삭제 중 오류가 발생했습니다."}), 500


@main_bp.route('/api/cart/update', methods=['POST'])
def update_cart_item():
    """
    장바구니 상품 수량 변경 API
    요청 본문: JSON { "cart_id": "...", "quantity": 2 } 또는 { "product_id": "...", "quantity": 2 }
    """
    data = request.get_json(silent=True) or {}
    item_id = data.get('cart_id') or data.get('product_id')
    quantity = int(data.get('quantity', 1))

    if not item_id:
        return jsonify({"success": False, "message": "항목 아이디가 필요합니다."}), 400

    user_id = _get_current_user_id()
    service_key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = get_supabase_client(use_service_role=bool(service_key))

    if user_id:
        try:
            # cart_id로 조회 시도
            c_res = supabase.table('carts').select('*, product_options(stock, stock_quantity)').eq('id', item_id).eq('user_id', user_id).maybe_single().execute()
            if not c_res or not c_res.data:
                c_res = supabase.table('carts').select('*, product_options(stock, stock_quantity)').eq('product_id', item_id).eq('user_id', user_id).maybe_single().execute()

            if c_res and c_res.data:
                item = c_res.data
                opt = item.get('product_options') or {}
                stk = opt.get('stock') if opt.get('stock') is not None else opt.get('stock_quantity', 999)
                stk = int(stk or 0)

                if quantity <= 0:
                    supabase.table('carts').delete().eq('id', item['id']).execute()
                else:
                    if quantity > stk:
                        return jsonify({"success": False, "message": f"재고가 부족합니다(현재 {stk}개)"}), 400
                    supabase.table('carts').update({'quantity': quantity}).eq('id', item['id']).execute()

                # 세션 카운트 동기화
                c_all = supabase.table('carts').select('product_id, quantity').eq('user_id', user_id).execute()
                cart = _get_cart()
                cart.clear()
                for r in (c_all.data or []):
                    cart[r['product_id']] = cart.get(r['product_id'], 0) + int(r['quantity'])
                session.modified = True
                return jsonify({"success": True, "cart_count": _get_cart_count(cart)})

        except Exception as e:
            logger.error("DB 장바구니 수량 변경 실패: %s", e)

    # 비로그인 세션 fallback
    cart = _get_cart()
    if quantity <= 0:
        cart.pop(item_id, None)
    else:
        cart[item_id] = quantity

    session.modified = True
    total_count = _get_cart_count(cart)
    return jsonify({
        "success": True,
        "cart_count": total_count
    })


@main_bp.route('/api/cart/remove', methods=['POST'])
def remove_from_cart():
    """
    장바구니 상품 개별 삭제 API
    요청 본문: JSON { "cart_id": "..." } 또는 { "product_id": "..." }
    """
    data = request.get_json(silent=True) or {}
    item_id = data.get('cart_id') or data.get('product_id')

    if not item_id:
        return jsonify({"success": False, "message": "상품 아이디가 필요합니다."}), 400

    user_id = _get_current_user_id()
    if user_id:
        try:
            service_key = os.getenv('SUPABASE_SERVICE_KEY')
            supabase = get_supabase_client(use_service_role=bool(service_key))
            supabase.table('carts').delete().eq('id', item_id).eq('user_id', user_id).execute()
            supabase.table('carts').delete().eq('product_id', item_id).eq('user_id', user_id).execute()

            # 세션 동기화
            c_all = supabase.table('carts').select('product_id, quantity').eq('user_id', user_id).execute()
            cart = _get_cart()
            cart.clear()
            for r in (c_all.data or []):
                cart[r['product_id']] = cart.get(r['product_id'], 0) + int(r['quantity'])
            session.modified = True
            return jsonify({
                "success": True,
                "message": "장바구니에서 상품이 삭제되었습니다.",
                "cart_count": _get_cart_count(cart)
            })
        except Exception as e:
            logger.error("DB 장바구니 항목 삭제 실패: %s", e)

    cart = _get_cart()
    cart.pop(item_id, None)
    session.modified = True

    total_count = _get_cart_count(cart)
    return jsonify({
        "success": True,
        "message": "장바구니에서 상품이 삭제되었습니다.",
        "cart_count": total_count
    })


@main_bp.route('/api/cart/delete-selected', methods=['POST'])
def delete_selected_cart_items():
    """
    선택된 장바구니 상품 일괄 삭제 API
    요청 본문: JSON { "cart_ids": ["...", "..."] }
    """
    data = request.get_json(silent=True) or {}
    cart_ids = data.get('cart_ids') or []
    if not cart_ids:
        return jsonify({"success": False, "message": "삭제할 상품을 선택해 주세요."}), 400

    user_id = _get_current_user_id()
    if user_id:
        try:
            service_key = os.getenv('SUPABASE_SERVICE_KEY')
            supabase = get_supabase_client(use_service_role=bool(service_key))
            # id 및 product_id 양쪽 조건 삭제 시도
            supabase.table('carts').delete().in_('id', cart_ids).eq('user_id', user_id).execute()
            supabase.table('carts').delete().in_('product_id', cart_ids).eq('user_id', user_id).execute()

            # 세션 동기화
            c_all = supabase.table('carts').select('product_id, quantity').eq('user_id', user_id).execute()
            cart = _get_cart()
            cart.clear()
            for r in (c_all.data or []):
                cart[r['product_id']] = cart.get(r['product_id'], 0) + int(r['quantity'])
            session.modified = True
            return jsonify({
                "success": True,
                "message": f"{len(cart_ids)}개의 상품이 삭제되었습니다.",
                "cart_count": _get_cart_count(cart)
            })
        except Exception as e:
            logger.error("선택 상품 일괄 삭제 실패: %s", e, exc_info=True)
            return jsonify({"success": False, "message": "상품 삭제 중 오류가 발생했습니다."}), 500

    # 비로그인 세션 기반
    cart = _get_cart()
    for cid in cart_ids:
        cart.pop(cid, None)
    session.modified = True

    return jsonify({
        "success": True,
        "message": f"{len(cart_ids)}개의 상품이 삭제되었습니다.",
        "cart_count": _get_cart_count(cart)
    })


@main_bp.route('/api/cart/clear', methods=['POST'])
def clear_cart():
    """
    장바구니 전체 삭제(비우기) API
    """
    user_id = _get_current_user_id()
    if user_id:
        try:
            service_key = os.getenv('SUPABASE_SERVICE_KEY')
            supabase = get_supabase_client(use_service_role=bool(service_key))
            supabase.table('carts').delete().eq('user_id', user_id).execute()
        except Exception as e:
            logger.error("장바구니 전체 삭제 실패: %s", e, exc_info=True)
            return jsonify({"success": False, "message": "장바구니 전체 삭제 중 오류가 발생했습니다."}), 500

    cart = _get_cart()
    cart.clear()
    session.modified = True

    return jsonify({
        "success": True,
        "message": "장바구니가 모두 비워졌습니다.",
        "cart_count": 0
    })


@main_bp.route('/api/cart/count', methods=['GET'])
def get_cart_count():
    """장바구니 전체 수량 조회 API"""
    return jsonify({"cart_count": _get_cart_count(_get_cart())})


# ------------------------------------------------------------------------------
# 마이페이지 (MYPAGE) 관련 헬퍼 함수
# ------------------------------------------------------------------------------
def _get_current_user_id() -> str | None:
    """세션에서 현재 로그인된 사용자의 ID를 안전하게 추출합니다."""
    return session.get('user_id') or session.get('user', {}).get('id')


def _fetch_user_profile(user_id: str) -> dict:
    """Supabase profiles 테이블에서 사용자 프로필을 조회합니다."""
    if not user_id:
        return {}
    try:
        supabase = get_supabase_client()
        res = supabase.table('profiles').select('*').eq('id', user_id).maybe_single().execute()
        return res.data if res and res.data else {}
    except Exception as e:
        logger.error("마이페이지 프로필 조회 실패 (user_id: %s): %s", user_id, e)
        return {}


def _update_user_profile(user_id: str, form_data: dict) -> tuple[bool, str]:
    """
    마이페이지 폼 데이터를 검증하고 profiles 테이블 및 세션에 반영합니다.
    (성공 여부, 결과 메시지) 튜플을 반환합니다.
    """
    name = form_data.get('name', '').strip()
    if not name:
        return False, '이름은 필수 입력 항목입니다.'

    phone = form_data.get('phone', '').strip()
    postal_code = form_data.get('postal_code', '').strip()
    address = form_data.get('address', '').strip()
    address_detail = form_data.get('address_detail', '').strip()

    update_payload = {
        'name': name,
        'phone': phone,
        'postal_code': postal_code,
        'address': address,
        'address_detail': address_detail
    }

    try:
        supabase = get_supabase_client()
        supabase.table('profiles').update(update_payload).eq('id', user_id).execute()

        # 세션 캐시 동기화
        if 'user' in session and isinstance(session['user'], dict):
            session['user']['name'] = name
            session.modified = True

        return True, '회원 정보가 성공적으로 수정되었습니다.'
    except Exception as e:
        logger.error("마이페이지 프로필 수정 실패 (user_id: %s): %s", user_id, e)
        return False, '회원 정보 수정 중 오류가 발생했습니다. 다시 시도해 주세요.'


def _is_email_user(user_id: str) -> bool:
    """
    사용자가 이메일/비밀번호 인증으로 가입한 회원인지 확인합니다.
    소셜 로그인(Kakao, Microsoft 등) 회원은 False를 반환합니다.
    """
    if not user_id:
        return False

    # 1. 세션 캐시 확인
    cached_provider = session.get('user', {}).get('provider')
    if cached_provider:
        return cached_provider == 'email'

    # 2. Supabase Admin API로 공급자 메타데이터 조회
    try:
        service_key = os.getenv('SUPABASE_SERVICE_KEY')
        if service_key:
            admin_client = get_supabase_client(use_service_role=True)
            user_res = admin_client.auth.admin.get_user_by_id(user_id)
            if user_res and user_res.user:
                app_meta = getattr(user_res.user, 'app_metadata', {}) or {}
                provider = app_meta.get('provider')
                if provider:
                    if 'user' in session and isinstance(session['user'], dict):
                        session['user']['provider'] = provider
                        session.modified = True
                    return provider == 'email'

                identities = getattr(user_res.user, 'identities', []) or []
                providers = [getattr(i, 'provider', '') for i in identities if getattr(i, 'provider', '')]
                if providers:
                    return 'email' in providers and len(providers) == 1
    except Exception as e:
        logger.warning("사용자 provider 확인 실패 (user_id: %s): %s", user_id, e)

    # 3. 소셜 가입 더미 이메일 패턴 확인
    user_email = session.get('user', {}).get('email', '')
    if '@kakao.user' in user_email or '@user.user' in user_email:
        return False

    return True


def _change_user_password(user_id: str, form_data: dict) -> tuple[bool, str]:
    """
    비밀번호 변경 비즈니스 로직을 처리합니다.
    - 입력값 및 일치 여부 검증
    - 기존 비밀번호 재로그인 검증
    - 새 비밀번호 정책 검증 (Day 1 가입 규칙과 동일)
    - Supabase update_user_by_id()를 통한 비밀번호 변경
    반환값: (성공 여부, 안내 메시지)
    """
    current_password = form_data.get('current_password', '').strip()
    new_password = form_data.get('new_password', '').strip()
    new_password_confirm = form_data.get('new_password_confirm', '').strip()

    # 1. 필수 입력 확인
    if not current_password or not new_password or not new_password_confirm:
        return False, '모든 필수 항목을 입력해 주세요.'

    # 2. 새 비밀번호와 기존 비밀번호 동일 여부 확인
    if current_password == new_password:
        return False, '새로운 비밀번호가 현재 비밀번호와 동일합니다.'

    # 3. 새 비밀번호와 비밀번호 확인 일치 검증
    if new_password != new_password_confirm:
        return False, '새 비밀번호와 비밀번호 확인이 일치하지 않습니다.'

    # 4. 사용자 이메일 획득
    user_email = session.get('user', {}).get('email')
    if not user_email or '@' not in user_email or user_email.endswith('.user'):
        profile = _fetch_user_profile(user_id)
        user_email = profile.get('email')

    # 5. 새 비밀번호 정책 검증 (최소 8자, 숫자/특수문자 포함, 이메일 불일치)
    policy_error = validate_password_policy(new_password, email=user_email)
    if policy_error:
        error_msg = ERROR_MESSAGES.get(policy_error, '비밀번호 규칙을 만족하지 않습니다.')
        return False, error_msg

    # 6. 기존 비밀번호 검증 (재로그인 방식)
    try:
        supabase = get_supabase_client()
        auth_res = supabase.auth.sign_in_with_password({
            "email": user_email,
            "password": current_password
        })
        if not auth_res or not auth_res.user:
            return False, '현재 비밀번호가 일치하지 않습니다.'
    except Exception as e:
        logger.warning("현재 비밀번호 검증 실패: %s", e)
        return False, '현재 비밀번호가 일치하지 않습니다.'

    # 7. Supabase update_user_by_id()로 비밀번호 갱신
    try:
        admin_client = get_supabase_client(use_service_role=True)
        admin_client.auth.admin.update_user_by_id(user_id, {
            "password": new_password
        })
        return True, '비밀번호가 변경되었습니다.'
    except Exception as e:
        logger.error("update_user_by_id 비밀번호 변경 실패: %s", e)
        return False, '비밀번호 변경 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'


# ------------------------------------------------------------------------------
# 마이페이지 (MYPAGE) 라우트
# ------------------------------------------------------------------------------
@main_bp.route('/mypage', methods=['GET', 'POST'])
@login_required
def mypage():
    """
    마이페이지 렌더링 및 프로필 수정 라우트
    로그인 세션을 확인하고 profiles 테이블에서 사용자 정보를 조회/수정합니다.
    """
    user_id = _get_current_user_id()

    # POST: 내 정보 수정 처리
    if request.method == 'POST':
        success, message = _update_user_profile(user_id, request.form)
        flash(message, 'success' if success else 'danger')
        return redirect(url_for('main.mypage'))

    # GET: 프로필 정보 조회
    profile = _fetch_user_profile(user_id)
    is_email_user = _is_email_user(user_id)

    # 주문 내역 조회
    orders = []
    try:
        service_key = os.getenv('SUPABASE_SERVICE_KEY')
        supabase = get_supabase_client(use_service_role=bool(service_key))
        orders_res = (
            supabase.table('orders')
            .select('*, order_items(*)')
            .eq('user_id', user_id)
            .order('created_at', desc=True)
            .execute()
        )
        orders = orders_res.data or []
        for o in orders:
            o['payment_amount_formatted'] = f"{int(float(o.get('payment_amount', 0))):,}원"
    except Exception as e:
        logger.error("마이페이지 주문 내역 조회 실패: %s", e)

    return render_template('mypage.html', profile=profile, is_email_user=is_email_user, orders=orders)


@main_bp.route('/mypage/change-password', methods=['POST'])
@login_required
def change_password():
    """
    마이페이지 비밀번호 변경 처리 라우트 (이메일/비밀번호 가입 회원 전용)
    """
    user_id = _get_current_user_id()
    if not user_id:
        flash('로그인이 필요합니다.', 'warning')
        return redirect(url_for('auth.login'))

    # 소셜 회원 차단
    if not _is_email_user(user_id):
        flash('소셜 로그인 계정은 비밀번호를 변경할 수 없습니다.', 'warning')
        return redirect(url_for('main.mypage'))

    success, message = _change_user_password(user_id, request.form)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('main.mypage'))



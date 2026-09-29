# app/routes/main.py - 메인 페이지 라우트 로직
"""
쇼핑몰 메인 페이지 및 기본 기능을 처리하는 라우트 모듈입니다.
Supabase에서 상품 데이터를 조회하여 템플릿에 전달합니다.
"""

import os
import sys
import logging
from flask import Blueprint, render_template, session, request, jsonify, redirect, url_for, flash
from dotenv import load_dotenv
from supabase import create_client, Client

# 로깅 설정
logger = logging.getLogger(__name__)

# 메인 블루프린트 생성
main_bp = Blueprint('main', __name__)

# .env 환경 변수 로드
load_dotenv()


def get_supabase_client() -> Client:
    """
    환경 변수로부터 Supabase 클라이언트를 초기화하여 반환합니다.
    """
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_anon_key = os.getenv('SUPABASE_ANON_KEY')

    if not supabase_url or not supabase_anon_key:
        raise ValueError("SUPABASE_URL 또는 SUPABASE_ANON_KEY 환경 변수가 설정되지 않았습니다.")

    return create_client(supabase_url, supabase_anon_key)


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
        formatted_products = []
        for item in raw_products:
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

            formatted_products.append({
                "id": item.get('id'),
                "name": item.get('name', '상품명 없음'),
                "price": display_price,
                "original_price": original_price_formatted,
                "has_discount": has_discount,
                "discount_pct": discount_pct,
                "thumbnail_url": item.get('thumbnail_url') or "/static/images/products/crop-tshirt.jpg",
                "description": item.get('description', ''),
                "status": item.get('status', 'active'),
                "sale_price": item.get('sale_price'),
                "raw_price": item.get('price')
            })

        return formatted_products

    except Exception as e:
        # 터미널에 에러 로그 출력 (앱 중단 방지)
        print(f"[ERROR] Supabase 상품 조회 실패: {e}", file=sys.stderr)
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

CATEGORY_TYPE_MAP = {
    1: {'name': '상의', 'code': 'top', 'badge_color': 'danger'},
    2: {'name': '바지', 'code': 'pants', 'badge_color': 'secondary'},
    3: {'name': '아우터', 'code': 'outer', 'badge_color': 'primary'},
    4: {'name': '원피스', 'code': 'dress', 'badge_color': 'info'},
    8: {'name': '치마', 'code': 'skirt', 'badge_color': 'warning'},
    5: {'name': '양말', 'code': 'socks', 'badge_color': 'success'}
}


def fetch_new_arrivals() -> list:
    """
    Supabase products 테이블에서 13개 신상품 목록을 조회하고 가공합니다.
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

    formatted = []
    for item in raw_products:
        cat_info = CATEGORY_TYPE_MAP.get(item.get('category_id'), {'name': '기타', 'code': 'etc', 'badge_color': 'dark'})
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

        formatted.append({
            'id': item.get('id'),
            'name': item.get('name'),
            'slug': item.get('slug'),
            'category_name': cat_info['name'],
            'category_code': cat_info['code'],
            'badge_color': cat_info['badge_color'],
            'price': display_price,
            'original_price': original_price_formatted,
            'has_discount': has_discount,
            'discount_pct': discount_pct,
            'thumbnail_url': item.get('thumbnail_url') or '/static/images/products/crop-tshirt.jpg',
            'description': item.get('description', ''),
            'status': item.get('status', 'active')
        })

    return formatted


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
    query = request.args.get('q', '').strip()
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

            for item in raw_products:
                cat_info = CATEGORY_TYPE_MAP.get(item.get('category_id'), {'name': '기타', 'code': 'etc', 'badge_color': 'dark'})
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

                formatted_products.append({
                    "id": item.get('id'),
                    "name": item.get('name', '상품명 없음'),
                    "slug": item.get('slug'),
                    "category_name": cat_info['name'],
                    "price": display_price,
                    "original_price": original_price_formatted,
                    "has_discount": has_discount,
                    "discount_pct": discount_pct,
                    "thumbnail_url": item.get('thumbnail_url') or "/static/images/products/crop-tshirt.jpg",
                    "description": item.get('description', ''),
                    "status": item.get('status', 'active')
                })
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
    next_grade_info = None

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

            for item in raw_products:
                cat_info = CATEGORY_TYPE_MAP.get(item.get('category_id'), {'name': '기타', 'code': 'etc', 'badge_color': 'dark'})
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

                products.append({
                    "id": item.get('id'),
                    "name": item.get('name', '상품명 없음'),
                    "slug": item.get('slug'),
                    "category_name": cat_info['name'],
                    "price": display_price,
                    "original_price": original_price_formatted,
                    "has_discount": has_discount,
                    "discount_pct": discount_pct,
                    "thumbnail_url": item.get('thumbnail_url') or "/static/images/products/crop-tshirt.jpg",
                    "description": item.get('description', ''),
                    "status": item.get('status', 'active')
                })
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


@main_bp.route('/cart')
def cart_view():
    """
    장바구니 페이지 렌더링 라우트
    세션에 저장된 상품 아이디들을 Supabase에서 조회하여 상세 정보와 합계 금액을 계산합니다.
    """
    cart = _get_cart()
    cart_items = []
    total_goods_price = 0

    if cart:
        product_ids = list(cart.keys())
        try:
            supabase = get_supabase_client()
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
                    "name": product.get('name', '상품명 없음'),
                    "unit_price": unit_price,
                    "unit_price_formatted": f"{unit_price:,}원",
                    "quantity": qty,
                    "subtotal": subtotal,
                    "subtotal_formatted": f"{subtotal:,}원",
                    "thumbnail_url": product.get('thumbnail_url') or "https://picsum.photos/seed/default/600/800",
                    "description": product.get('description', '')
                })
        except Exception as e:
            logger.error("장바구니 상품 조회 실패: %s", e, exc_info=True)

    # 배송비 정책: 50,000원 이상 구매 시 무료 배송 (미만 시 3,000원)
    shipping_fee = 0 if (total_goods_price >= 50000 or total_goods_price == 0) else 3000
    final_payment_amount = total_goods_price + shipping_fee

    return render_template(
        'cart.html',
        cart_items=cart_items,
        total_goods_price=total_goods_price,
        total_goods_price_formatted=f"{total_goods_price:,}원",
        shipping_fee=shipping_fee,
        shipping_fee_formatted=f"{shipping_fee:,}원" if shipping_fee > 0 else "무료",
        final_payment_amount=final_payment_amount,
        final_payment_amount_formatted=f"{final_payment_amount:,}원"
    )


@main_bp.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    """
    장바구니 상품 추가 API
    요청 본문: JSON { "product_id": "...", "quantity": 1 }
    """
    from flask import request, jsonify

    data = request.get_json(silent=True) or {}
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))

    if not product_id or quantity <= 0:
        return jsonify({"success": False, "message": "유효하지 않은 요청입니다."}), 400

    cart = _get_cart()
    cart[product_id] = cart.get(product_id, 0) + quantity
    session.modified = True

    total_count = sum(cart.values())
    return jsonify({
        "success": True,
        "message": "장바구니에 상품이 추가되었습니다.",
        "cart_count": total_count
    })


@main_bp.route('/api/cart/update', methods=['POST'])
def update_cart_item():
    """
    장바구니 상품 수량 변경 API
    요청 본문: JSON { "product_id": "...", "quantity": 2 }
    """
    from flask import request, jsonify

    data = request.get_json(silent=True) or {}
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))

    if not product_id:
        return jsonify({"success": False, "message": "상품 아이디가 필요합니다."}), 400

    cart = _get_cart()
    if quantity <= 0:
        cart.pop(product_id, None)
    else:
        cart[product_id] = quantity

    session.modified = True
    total_count = sum(cart.values())
    return jsonify({
        "success": True,
        "cart_count": total_count
    })


@main_bp.route('/api/cart/remove', methods=['POST'])
def remove_from_cart():
    """
    장바구니 상품 개별 삭제 API
    요청 본문: JSON { "product_id": "..." }
    """
    from flask import request, jsonify

    data = request.get_json(silent=True) or {}
    product_id = data.get('product_id')

    if not product_id:
        return jsonify({"success": False, "message": "상품 아이디가 필요합니다."}), 400

    cart = _get_cart()
    cart.pop(product_id, None)
    session.modified = True

    total_count = sum(cart.values())
    return jsonify({
        "success": True,
        "message": "장바구니에서 상품이 삭제되었습니다.",
        "cart_count": total_count
    })


@main_bp.route('/api/cart/count', methods=['GET'])
def get_cart_count():
    """장바구니 전체 수량 조회 API"""
    from flask import jsonify
    cart = _get_cart()
    return jsonify({"cart_count": sum(cart.values())})


# ------------------------------------------------------------------------------
# 마이페이지 (MYPAGE) 라우트
# ------------------------------------------------------------------------------
@main_bp.route('/mypage')
def mypage():
    """
    마이페이지 렌더링 라우트
    로그인 세션을 확인하고 프로필 정보 및 위시리스트/장바구니 요약을 제공합니다.
    """
    from app.routes.auth import login_required

    @login_required
    def _mypage_view():
        return render_template('mypage.html')

    return _mypage_view()



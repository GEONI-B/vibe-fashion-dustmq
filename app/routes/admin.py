# app/routes/admin.py - 관리자 기능 및 접근제어 라우트
"""
VIBE FASHION 관리자 전용 라우트 및 서버 측 권한 제어 모듈입니다.
"""

from functools import wraps
import logging
import uuid
import re
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, session, request, redirect, url_for, flash, abort
from app.supabase_client import get_supabase_client
from app.routes.auth import _save_user_session, _clear_auth_session

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def get_user_role_from_db(user_id: str) -> str | None:
    """
    서버 DB(profiles 테이블)에서 사용자의 현재 role을 실시간 조회합니다.
    (보안: session/브라우저 값에 의존하지 않으며, anon/사용자 세션 클라이언트를 사용하여 RLS 정책 준수)
    """
    if not user_id:
        return None
    try:
        supabase = get_supabase_client()
        res = supabase.table('profiles').select('role').eq('id', user_id).maybe_single().execute()
        if res and res.data:
            return res.data.get('role')
        return None
    except Exception as e:
        logger.error("DB profiles.role 조회 실패 (user_id: %s): %s", user_id, e)
        return None


def admin_required(f):
    """
    관리자 권한 검사 데코레이터
    1. 로그인 여부 확인 -> 비로그인 시 /admin/login 으로 리다이렉트
    2. 서버 DB(profiles)에서 실시간 role 조회 -> admin이 아니면 403 Forbidden 반환
    (Service Role 사용 금지, 세션 role 신뢰 금지)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id') or (session.get('user', {}).get('id') if isinstance(session.get('user'), dict) else None)
        if not user_id:
            return redirect(url_for('admin.admin_login', next=request.url))

        role = get_user_role_from_db(user_id)
        if role != 'admin':
            logger.warning("관리자 권한 없는 접근 차단 (user_id: %s, role: %s, path: %s)", user_id, role, request.path)
            abort(403, description="관리자 권한이 없습니다.")

        return f(*args, **kwargs)
    return decorated_function


# ------------------------------------------------------------------------------
# [1] GET/POST /admin/login - 관리자 로그인
# ------------------------------------------------------------------------------
@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """
    관리자 로그인 화면 및 인증 처리
    - 일반 회원가입 없음
    - Supabase 이메일/비밀번호 인증 재사용
    - 인증 성공 후 서버에서 profiles.role 확인 -> admin만 로그인 허용
    - customer 계정인 경우 세션 정리 후 경고 메시지와 함께 차단
    """
    next_url = request.args.get('next')

    # 이미 관리자로 로그인되어 있는지 DB에서 확인
    current_user_id = session.get('user_id') or (session.get('user', {}).get('id') if isinstance(session.get('user'), dict) else None)
    if current_user_id:
        current_role = get_user_role_from_db(current_user_id)
        if current_role == 'admin':
            return redirect(next_url or url_for('admin.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('이메일과 비밀번호를 모두 입력해 주세요.', 'danger')
            return render_template('admin/login.html', email=email, next=next_url)

        try:
            supabase = get_supabase_client()
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            user = response.user
            auth_session = response.session

            if user:
                # 이메일 인증 여부 검사
                is_confirmed = bool(getattr(user, 'email_confirmed_at', None) or getattr(user, 'confirmed_at', None))
                if not is_confirmed:
                    try:
                        supabase.auth.sign_out()
                    except Exception:
                        pass
                    flash('이메일 인증이 완료되지 않은 계정입니다.', 'warning')
                    return render_template('admin/login.html', email=email, next=next_url)

                # 서버 DB(profiles.role) 검증 (Service Role 미사용)
                prof_res = supabase.table('profiles').select('role').eq('id', user.id).maybe_single().execute()
                user_role = prof_res.data.get('role') if (prof_res and prof_res.data) else None

                if user_role != 'admin':
                    # 관리자가 아닌 일반 customer 계정인 경우 즉시 로그아웃 처리
                    try:
                        supabase.auth.sign_out()
                    except Exception:
                        pass
                    _clear_auth_session()
                    logger.warning("관리자 로그인 시도 거부: 일반 회원 계정 (user_id: %s, role: %s)", user.id, user_role)
                    flash('관리자 권한이 없는 계정입니다.', 'danger')
                    return render_template('admin/login.html', email=email, next=next_url)

                # admin 계정 확인 완료 -> 세션 저장
                _save_user_session(user, auth_session)
                flash('관리자님, 환영합니다.', 'success')
                safe_next = next_url if (next_url and next_url.startswith('/') and not next_url.startswith('//')) else None
                return redirect(safe_next or url_for('admin.dashboard'))

        except Exception as e:
            error_msg = str(e).lower()
            logger.error("관리자 로그인 실패: %s", e)
            if 'invalid' in error_msg or 'credentials' in error_msg or 'grant' in error_msg:
                flash('이메일 또는 비밀번호가 일치하지 않습니다.', 'danger')
            elif 'email not confirmed' in error_msg or 'email_not_confirmed' in error_msg:
                flash('이메일 인증이 완료되지 않은 계정입니다.', 'warning')
            else:
                flash('로그인 처리 중 오류가 발생했습니다. 다시 시도해 주세요.', 'danger')

            return render_template('admin/login.html', email=email, next=next_url)

    return render_template('admin/login.html', next=next_url)


# ------------------------------------------------------------------------------
# [2] GET /admin - 관리자 대시보드 1차
# ------------------------------------------------------------------------------
@admin_bp.route('')
@admin_bp.route('/')
@admin_required
def dashboard():
    """
    관리자 1차 대시보드 라우트
    반드시 admin_required 뒤에서 실행되며, 관리자 확인 후에만 데이터 조회.
    - 오늘 주문 건수 및 오늘 매출 (orders 테이블)
    - 오늘 신규 회원 수 (profiles 테이블)
    - 품절 옵션 수 (재고 = 0)
    - 재고 부족 옵션 수 (1 <= 재고 <= 5)
    - 최근 주문 5건
    - 재고 부족/품절 옵션 목록
    """
    supabase = get_supabase_client()

    summary = {
        'today_orders_count': 0,
        'today_sales_amount': 0,
        'today_new_users_count': 0,
        'sold_out_count': 0,
        'low_stock_count': 0
    }
    recent_orders = []
    low_stock_items = []

    # KST(UTC+9) 기준 오늘의 시작 시각 계산 후 UTC 변환
    tz_kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(tz_kst)
    today_start_kst = datetime(now_kst.year, now_kst.month, now_kst.day, 0, 0, 0, tzinfo=tz_kst)
    today_start_iso = today_start_kst.astimezone(timezone.utc).isoformat()

    try:
        # 1. 오늘 주문 통계 조회 (orders)
        orders_today_res = (
            supabase.table('orders')
            .select('id, payment_amount, status, created_at')
            .gte('created_at', today_start_iso)
            .execute()
        )
        orders_today = orders_today_res.data or []
        summary['today_orders_count'] = len(orders_today)
        summary['today_sales_amount'] = sum(
            int(float(o.get('payment_amount', 0)))
            for o in orders_today
            if o.get('status') in ['paid', 'preparing', 'shipping', 'delivered']
        )

        # 2. 오늘 신규 가입 회원 수 조회 (profiles)
        profiles_today_res = (
            supabase.table('profiles')
            .select('id', count='exact')
            .gte('created_at', today_start_iso)
            .execute()
        )
        summary['today_new_users_count'] = profiles_today_res.count if profiles_today_res.count is not None else len(profiles_today_res.data or [])

        # 3. 상품 옵션 재고 통계 (product_options + products 이름)
        # 0 = 품절, 1~5 = 재고 부족
        options_res = (
            supabase.table('product_options')
            .select('id, product_id, option_name, stock_quantity, products(name)')
            .lte('stock_quantity', 5)
            .order('stock_quantity', desc=False)
            .execute()
        )
        low_and_sold_rows = options_res.data or []

        sold_out_list = []
        low_stock_list = []

        for row in low_and_sold_rows:
            stock = int(row.get('stock_quantity', 0) or 0)
            product_data = row.get('products') or {}
            p_name = product_data.get('name') if isinstance(product_data, dict) else '상품명 미확인'

            formatted_item = {
                'id': row.get('id'),
                'product_name': p_name,
                'option_name': row.get('option_name', '기본'),
                'stock_quantity': stock
            }

            if stock == 0:
                sold_out_list.append(formatted_item)
            elif 1 <= stock <= 5:
                low_stock_list.append(formatted_item)

        summary['sold_out_count'] = len(sold_out_list)
        summary['low_stock_count'] = len(low_stock_list)
        low_stock_items = (sold_out_list + low_stock_list)[:10]

        # 4. 최근 주문 5건 조회 (orders)
        recent_orders_res = (
            supabase.table('orders')
            .select('id, order_number, recipient_name, payment_amount, status, created_at')
            .order('created_at', desc=True)
            .limit(5)
            .execute()
        )
        recent_orders = recent_orders_res.data or []

    except Exception as e:
        logger.error("대시보드 통계 조회 중 오류 발생: %s", e, exc_info=True)
        # 데이터베이스 조회에 실패하더라도 화면이 깨지지 않고 0건으로 정상 렌더링되도록 보호

    return render_template(
        'admin/index.html',
        active_menu='dashboard',
        summary=summary,
        recent_orders=recent_orders,
        low_stock_items=low_stock_items
    )


# ------------------------------------------------------------------------------
# [3] GET /admin/products - 상품 관리 (목록/검색/필터)
# ------------------------------------------------------------------------------
@admin_bp.route('/products')
@admin_required
def products_list():
    """
    관리자 상품 목록 라우트
    - admin_required 적용
    - 상품명 검색 (q)
    - 카테고리 필터 (category_id)
    - 판매상태 필터 (status: active, sold_out, hidden)
    - 최소 페이지네이션 (한 페이지 10개)
    - 상품이 없어도 오류 없이 빈 상태 표시
    """
    admin_supabase = get_supabase_client(use_service_role=True)

    q = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', '').strip()
    status = request.args.get('status', '').strip()

    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1

    per_page = 10
    offset = (page - 1) * per_page

    categories = []
    products = []
    total_count = 0

    try:
        # 카테고리 목록 조회 (필터 셀렉트 박스용)
        cat_res = admin_supabase.table('categories').select('id, name').order('display_order', desc=False).execute()
        categories = cat_res.data or []

        # 상품 쿼리 구성 (admin_required 통과 후 관리자 목록 조회: hidden 포함 전체 조회)
        query = admin_supabase.table('products').select(
            'id, category_id, name, slug, price, sale_price, status, thumbnail_url, categories(name)',
            count='exact'
        )

        if q:
            query = query.ilike('name', f"%{q}%")
        if category_id:
            query = query.eq('category_id', category_id)
        if status:
            query = query.eq('status', status)

        prod_res = query.order('created_at', desc=True).range(offset, offset + per_page - 1).execute()

        raw_products = prod_res.data or []
        total_count = prod_res.count if prod_res.count is not None else len(raw_products)

        for p in raw_products:
            cat_data = p.get('categories') or {}
            cat_name = cat_data.get('name') if isinstance(cat_data, dict) else '미지정'
            products.append({
                'id': p.get('id'),
                'name': p.get('name', '상품명 없음'),
                'slug': p.get('slug'),
                'category_name': cat_name,
                'price': int(float(p.get('price', 0))),
                'sale_price': int(float(p.get('sale_price'))) if p.get('sale_price') is not None else None,
                'status': p.get('status', 'active'),
                'thumbnail_url': p.get('thumbnail_url')
            })

    except Exception as e:
        logger.error("관리자 상품 목록 조회 실패: %s", e, exc_info=True)

    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return render_template(
        'admin/products.html',
        active_menu='products',
        categories=categories,
        products=products,
        total_count=total_count,
        current_page=page,
        total_pages=total_pages,
        query_params={
            'q': q,
            'category_id': category_id,
            'status': status
        }
    )


# ------------------------------------------------------------------------------
# [4] GET/POST /admin/products/new - 상품 기본정보 등록
# ------------------------------------------------------------------------------
@admin_bp.route('/products/new', methods=['GET', 'POST'])
@admin_required
def product_new():
    """
    관리자 상품 기본정보 등록 라우트
    - admin_required 적용
    - 입력: name, category_id, description, price, sale_price
    - status는 무조건 'hidden'으로 저장 (옵션/재고 미보유 상태 보호)
    - slug: 타임스탬프와 6자리 랜덤 UUID 접미사 기반 고유 slug 자동 생성
    - 검증 실패 시: 입력값 유지 및 오류 표시
    - 저장 성공 시: /admin/products 로 리다이렉트
    """
    supabase = get_supabase_client()

    categories = []
    try:
        cat_res = supabase.table('categories').select('id, name').order('display_order', desc=False).execute()
        categories = cat_res.data or []
    except Exception as e:
        logger.error("카테고리 목록 조회 실패: %s", e)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id_raw = request.form.get('category_id', '').strip()
        price_raw = request.form.get('price', '').strip()
        sale_price_raw = request.form.get('sale_price', '').strip()
        description = request.form.get('description', '').strip()

        errors = {}

        # 1. 상품명 필수 검증
        if not name:
            errors['name'] = '상품명을 입력해 주세요.'

        # 2. 카테고리 필수 검증
        category_id = None
        if not category_id_raw:
            errors['category_id'] = '카테고리를 선택해 주세요.'
        else:
            try:
                category_id = int(category_id_raw)
            except (ValueError, TypeError):
                errors['category_id'] = '유효한 카테고리를 선택해 주세요.'

        # 3. 정상가 필수 + 0 이상 숫자 검증
        price = None
        if not price_raw:
            errors['price'] = '정상가를 입력해 주세요.'
        else:
            try:
                price = float(price_raw)
                if price < 0:
                    errors['price'] = '정상가는 0원 이상이어야 합니다.'
            except (ValueError, TypeError):
                errors['price'] = '정상가는 유효한 숫자로 입력해 주세요.'

        # 4. 할인가 검증 (입력 시 0 이상, 정상가 이하)
        sale_price = None
        if sale_price_raw:
            try:
                sale_price = float(sale_price_raw)
                if sale_price < 0:
                    errors['sale_price'] = '할인가는 0원 이상이어야 합니다.'
                elif price is not None and sale_price > price:
                    errors['sale_price'] = '할인가는 정상가보다 클 수 없습니다.'
            except (ValueError, TypeError):
                errors['sale_price'] = '할인가는 유효한 숫자로 입력해 주세요.'

        # 검증 오류가 있으면 입력값 유지 후 재렌더링
        if errors:
            return render_template(
                'admin/product_form.html',
                active_menu='products',
                categories=categories,
                form_data=request.form,
                errors=errors
            )

        # 5. 고유 slug 생성: 'prod-' + 타임스탬프(YYYYMMDDHHMMSS) + '-' + 6자리 uuid
        now_utc = datetime.now(timezone.utc)
        unique_suffix = uuid.uuid4().hex[:6]
        slug = f"prod-{now_utc.strftime('%Y%m%d%H%M%S')}-{unique_suffix}"

        # 6. products 테이블에 저장 (status는 무조건 hidden)
        # admin_required를 통해 DB role=admin 검증 통과 후에만 Service Role 클라이언트로 INSERT 수행
        insert_payload = {
            'name': name,
            'category_id': category_id,
            'description': description or None,
            'price': price,
            'sale_price': sale_price,
            'slug': slug,
            'status': 'hidden'  # 신규 등록 상품은 무조건 hidden으로 저장
        }

        try:
            admin_supabase = get_supabase_client(use_service_role=True)
            insert_res = admin_supabase.table('products').insert(insert_payload).execute()
            if not insert_res or not insert_res.data:
                raise Exception("상품 데이터 저장 결과가 올바르지 않습니다.")

            flash(f"상품 '{name}'이(가) 등록되었습니다. (상태: 숨김)", 'success')
            return redirect(url_for('admin.products_list'))

        except Exception as e:
            logger.error("상품 등록 실패: %s", e, exc_info=True)
            flash('상품 등록 중 오류가 발생했습니다. 다시 시도해 주세요.', 'danger')
            return render_template(
                'admin/product_form.html',
                active_menu='products',
                categories=categories,
                form_data=request.form,
                errors={'general': '상품 저장 중 오류가 발생했습니다.'}
            )

    # GET 요청: 신규 등록 폼 렌더링
    return render_template(
        'admin/product_form.html',
        active_menu='products',
        categories=categories,
        form_data={},
        errors={}
    )


# ------------------------------------------------------------------------------
# [5] GET/POST /admin/products/<product_id>/edit - 상품 기본정보 및 판매상태 수정
# ------------------------------------------------------------------------------
@admin_bp.route('/products/<product_id>/edit', methods=['GET', 'POST'])
@admin_required
def product_edit(product_id: str):
    """
    관리자 상품 정보 수정 라우트
    - admin_required 적용
    - 관리자 권한 검증 통과 후 해당 상품 조회 및 UPDATE에 Service Role 사용
    - 수정 가능 항목: name, category_id, description, price, sale_price, status
    - status 허용값: active, sold_out, hidden
    - slug, thumbnail_url 유지 (수정 불가)
    - active 전환 안전장치:
      상품을 'active'로 변경하려는 경우 해당 상품의 product_options 확인
      (옵션이 존재하고 stock_quantity > 0인 옵션이 최소 1개 이상 있어야 변경 가능)
    - 존재하지 않는 상품: 404 처리
    """
    admin_supabase = get_supabase_client(use_service_role=True)

    # 1. 대상 상품 조회 (존재 여부 확인)
    try:
        prod_res = (
            admin_supabase.table('products')
            .select('*')
            .eq('id', product_id)
            .maybe_single()
            .execute()
        )
        if not prod_res or not prod_res.data:
            abort(404, description="수정할 상품을 찾을 수 없습니다.")
        product = prod_res.data
    except Exception as e:
        logger.error("상품 조회 실패 (id: %s): %s", product_id, e, exc_info=True)
        abort(404, description="상품을 찾을 수 없습니다.")

    # 카테고리 목록 조회
    categories = []
    try:
        cat_res = admin_supabase.table('categories').select('id, name').order('display_order', desc=False).execute()
        categories = cat_res.data or []
    except Exception as e:
        logger.error("카테고리 목록 조회 실패: %s", e)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id_raw = request.form.get('category_id', '').strip()
        price_raw = request.form.get('price', '').strip()
        sale_price_raw = request.form.get('sale_price', '').strip()
        status = request.form.get('status', '').strip()
        description = request.form.get('description', '').strip()

        errors = {}

        # 상품명 검증
        if not name:
            errors['name'] = '상품명을 입력해 주세요.'

        # 카테고리 검증
        category_id = None
        if not category_id_raw:
            errors['category_id'] = '카테고리를 선택해 주세요.'
        else:
            try:
                category_id = int(category_id_raw)
            except (ValueError, TypeError):
                errors['category_id'] = '유효한 카테고리를 선택해 주세요.'

        # 정상가 검증 (0 이상)
        price = None
        if not price_raw:
            errors['price'] = '정상가를 입력해 주세요.'
        else:
            try:
                price = float(price_raw)
                if price < 0:
                    errors['price'] = '정상가는 0원 이상이어야 합니다.'
            except (ValueError, TypeError):
                errors['price'] = '정상가는 유효한 숫자로 입력해 주세요.'

        # 할인가 검증 (입력 시 0 이상, 정상가 이하)
        sale_price = None
        if sale_price_raw:
            try:
                sale_price = float(sale_price_raw)
                if sale_price < 0:
                    errors['sale_price'] = '할인가는 0원 이상이어야 합니다.'
                elif price is not None and sale_price > price:
                    errors['sale_price'] = '할인가는 정상가보다 클 수 없습니다.'
            except (ValueError, TypeError):
                errors['sale_price'] = '할인가는 유효한 숫자로 입력해 주세요.'

        # 판매상태 값 허용 목록 검증
        allowed_statuses = ('active', 'sold_out', 'hidden')
        if status not in allowed_statuses:
            errors['status'] = '유효한 판매상태(active, sold_out, hidden)를 선택해 주세요.'

        # active 전환 안전장치 검증:
        # 상태를 'active'로 설정하려는 경우 (기존 상태가 아니었거나, 기존 상태여도 활성 상태 유지 시 검증)
        if status == 'active' and not errors.get('status'):
            try:
                opt_res = (
                    admin_supabase.table('product_options')
                    .select('id, stock_quantity')
                    .eq('product_id', product_id)
                    .execute()
                )
                options = opt_res.data or []
                has_in_stock_option = any(
                    int(opt.get('stock_quantity', 0) or 0) > 0 for opt in options
                )

                if not options or not has_in_stock_option:
                    errors['status'] = '판매 가능한 옵션과 재고를 먼저 등록해 주세요.'
            except Exception as opt_err:
                logger.error("옵션 및 재고 확인 실패 (product_id: %s): %s", product_id, opt_err)
                errors['status'] = '옵션 및 재고 확인 중 오류가 발생했습니다.'

        # 검증 실패 시 입력값 유지 후 오류 표시 (DB UPDATE 금지)
        if errors:
            return render_template(
                'admin/product_edit.html',
                active_menu='products',
                product=product,
                categories=categories,
                form_data=request.form,
                errors=errors
            )

        # UPDATE 페이로드 구성 (slug, thumbnail_url은 변경하지 않음)
        update_payload = {
            'name': name,
            'category_id': category_id,
            'description': description or None,
            'price': price,
            'sale_price': sale_price,
            'status': status
        }

        try:
            update_res = admin_supabase.table('products').update(update_payload).eq('id', product_id).execute()
            if not update_res or not update_res.data:
                raise Exception("상품 수정 업데이트 결과가 올바르지 않습니다.")

            flash(f"상품 '{name}' 정보가 성공적으로 수정되었습니다.", 'success')
            return redirect(url_for('admin.products_list'))

        except Exception as update_err:
            logger.error("상품 수정 실패 (id: %s): %s", product_id, update_err, exc_info=True)
            flash('상품 정보 수정 중 오류가 발생했습니다. 다시 시도해 주세요.', 'danger')
            return render_template(
                'admin/product_edit.html',
                active_menu='products',
                product=product,
                categories=categories,
                form_data=request.form,
                errors={'general': '상품 정보 수정 중 오류가 발생했습니다.'}
            )

    # GET 요청: 기존 상품 데이터 바인딩하여 폼 렌더링
    initial_form_data = {
        'name': product.get('name', ''),
        'category_id': str(product.get('category_id') or ''),
        'price': int(float(product.get('price', 0))),
        'sale_price': int(float(product.get('sale_price'))) if product.get('sale_price') is not None else '',
        'status': product.get('status', 'hidden'),
        'description': product.get('description', '') or ''
    }

    return render_template(
        'admin/product_edit.html',
        active_menu='products',
        product=product,
        categories=categories,
        form_data=initial_form_data,
        errors={}
    )


# ------------------------------------------------------------------------------
# [6] GET /admin/inventory - 관리자 옵션 / 재고 목록 조회
# ------------------------------------------------------------------------------
@admin_bp.route('/inventory')
@admin_required
def inventory_list():
    """
    관리자 옵션 및 재고 목록 조회 라우트
    - admin_required 적용
    - Service Role client를 사용하여 product_options 및 연결된 products 조회
    - 상품명 검색 (q)
    - 재고 상태 필터 (stock_status: sold_out, low_stock, normal)
    - 재고 상태 계산:
      * 0: 품절 (sold_out)
      * 1~5: 재고 부족 (low_stock)
      * 6 이상: 정상 (normal)
    - 페이지네이션 적용 (한 페이지 15개)
    - 0건일 때 오류 없이 빈 상태 표시
    """
    admin_supabase = get_supabase_client(use_service_role=True)

    q = request.args.get('q', '').strip()
    stock_status = request.args.get('stock_status', '').strip()

    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1

    per_page = 15

    items = []
    total_count = 0

    try:
        # product_options 및 연결된 products(name) 조회
        query = (
            admin_supabase.table('product_options')
            .select('id, product_id, option_name, sku, stock_quantity, created_at, products!inner(name)')
        )

        # 1. 상품명 검색 (연결된 products.name 대상)
        if q:
            query = query.ilike('products.name', f"%{q}%")

        # 2. 재고 상태 필터 (DB 쿼리 레벨 적용)
        # stock_quantity 기준: 0(품절), 1~5(재고 부족), 6 이상(정상)
        if stock_status == 'sold_out':
            query = query.eq('stock_quantity', 0)
        elif stock_status == 'low_stock':
            query = query.gte('stock_quantity', 1).lte('stock_quantity', 5)
        elif stock_status == 'normal':
            query = query.gte('stock_quantity', 6)

        # 전체 일치 데이터 조회 (정렬: 상품명 오름차순, 옵션명 오름차순)
        res = query.order('stock_quantity', desc=False).execute()
        raw_items = res.data or []
        total_count = len(raw_items)

        # 페이지네이션 슬라이싱
        offset = (page - 1) * per_page
        paged_rows = raw_items[offset:offset + per_page]

        for r in paged_rows:
            stock = int(r.get('stock_quantity', 0) or 0)
            product_data = r.get('products') or {}
            p_name = product_data.get('name') if isinstance(product_data, dict) else '상품명 미확인'

            # 화면용 재고 상태 계산 (0: sold_out, 1~5: low_stock, 6+: normal)
            if stock == 0:
                calc_status = 'sold_out'
            elif 1 <= stock <= 5:
                calc_status = 'low_stock'
            else:
                calc_status = 'normal'

            items.append({
                'id': r.get('id'),
                'product_id': r.get('product_id'),
                'product_name': p_name,
                'option_name': r.get('option_name', '-'),
                'sku': r.get('sku'),
                'stock_quantity': stock,
                'stock_status': calc_status
            })

    except Exception as e:
        logger.error("관리자 재고 목록 조회 실패: %s", e, exc_info=True)

    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return render_template(
        'admin/inventory.html',
        active_menu='inventory',
        items=items,
        total_count=total_count,
        current_page=page,
        total_pages=total_pages,
        query_params={
            'q': q,
            'stock_status': stock_status
        }
    )


@admin_bp.route('/inventory/<option_id>/stock', methods=['POST'])
@admin_required
def inventory_update_stock(option_id):
    stock_quantity_raw = request.form.get('stock_quantity', '').strip()
    try:
        stock_quantity = int(stock_quantity_raw)
        if stock_quantity < 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('재고 수량은 0 이상의 정수로 입력해 주세요.', 'danger')
        return redirect(url_for(
            'admin.inventory_list',
            q=request.form.get('q', ''),
            stock_status=request.form.get('stock_status', ''),
            page=request.form.get('page', 1)
        ))

    try:
        admin_supabase = get_supabase_client(use_service_role=True)
        admin_supabase.table('product_options').update(
            {'stock_quantity': stock_quantity}
        ).eq('id', option_id).execute()
        flash('재고 수량이 수정되었습니다.', 'success')
    except Exception as e:
        logger.error("관리자 재고 수정 실패 (option_id: %s): %s", option_id, e, exc_info=True)
        flash('재고 수정 중 오류가 발생했습니다. 다시 시도해 주세요.', 'danger')

    return redirect(url_for(
        'admin.inventory_list',
        q=request.form.get('q', ''),
        stock_status=request.form.get('stock_status', ''),
        page=request.form.get('page', 1)
    ))


# ------------------------------------------------------------------------------
# [7] GET/POST /admin/inventory/new - 상품 옵션 등록
# ------------------------------------------------------------------------------
@admin_bp.route('/inventory/new', methods=['GET', 'POST'])
@admin_required
def inventory_new():
    """
    관리자 상품 옵션 등록 라우트
    - admin_required 적용
    - 관리자 검증 후 DB 작업에 Service Role 사용
    - 입력: product_id(필수), color(필수), size(필수), stock_quantity(필수, 0 이상 정수),
            additional_price(선택, 기본 0), sku(선택)
    - option_name 조합: "{color} / {size}" 형태로 저장
    - 검증:
      * 상품 필수 및 실제 products 테이블에 존재하는지 확인
      * 색상, 사이즈 필수
      * 추가금액 숫자
      * 초기 재고 0 이상 정수
      * 동일 상품 내 동일 option_name 중복 차단
      * SKU 입력 시 기존 SKU와 중복 여부 확인
    - 저장: product_options 테이블에 INSERT
    - 상품 상태: products.status 자동 변경 금지 (기존 상태 유지)
    - 성공: /admin/inventory 리다이렉트 및 성공 메시지
    - 실패: 입력값 유지 및 오류 표시
    """
    admin_supabase = get_supabase_client(use_service_role=True)

    products = []
    try:
        prod_res = (
            admin_supabase.table('products')
            .select('id, name, status')
            .order('name', desc=False)
            .execute()
        )
        products = prod_res.data or []
    except Exception as e:
        logger.error("옵션 등록용 상품 목록 조회 실패: %s", e)

    if request.method == 'POST':
        product_id = request.form.get('product_id', '').strip()
        color = request.form.get('color', '').strip()
        size = request.form.get('size', '').strip()
        stock_qty_raw = request.form.get('stock_quantity', '').strip()
        add_price_raw = request.form.get('additional_price', '').strip()
        sku = request.form.get('sku', '').strip()

        errors = {}

        # 1. 상품 선택 필수 및 DB 존재 여부 검증
        if not product_id:
            errors['product_id'] = '옵션을 등록할 상품을 선택해 주세요.'
        else:
            try:
                chk_prod = admin_supabase.table('products').select('id, name').eq('id', product_id).maybe_single().execute()
                if not chk_prod or not chk_prod.data:
                    errors['product_id'] = '선택한 상품이 존재하지 않습니다.'
            except Exception as chk_err:
                logger.error("상품 존재 여부 확인 실패 (product_id: %s): %s", product_id, chk_err)
                errors['product_id'] = '상품 확인 중 오류가 발생했습니다.'

        # 2. 색상, 사이즈 필수 검증
        if not color:
            errors['color'] = '색상을 입력해 주세요.'
        if not size:
            errors['size'] = '사이즈를 입력해 주세요.'

        # 3. 추가금액 숫자 검증 (기본 0)
        additional_price = 0.0
        if add_price_raw:
            try:
                additional_price = float(add_price_raw)
            except (ValueError, TypeError):
                errors['additional_price'] = '추가 금액은 올바른 숫자로 입력해 주세요.'

        # 4. 초기 재고 0 이상 정수 검증
        stock_quantity = None
        if not stock_qty_raw:
            errors['stock_quantity'] = '초기 재고 수량을 입력해 주세요.'
        else:
            try:
                stock_quantity = int(stock_qty_raw)
                if stock_quantity < 0:
                    errors['stock_quantity'] = '재고 수량은 0 이상의 정수여야 합니다.'
            except (ValueError, TypeError):
                errors['stock_quantity'] = '재고 수량은 올바른 정수로 입력해 주세요.'

        # 5. option_name 조합 및 동일 상품 내 중복 검증
        option_name = None
        if color and size:
            option_name = f"{color} / {size}"
            if product_id and not errors.get('product_id'):
                try:
                    dup_res = (
                        admin_supabase.table('product_options')
                        .select('id')
                        .eq('product_id', product_id)
                        .eq('option_name', option_name)
                        .maybe_single()
                        .execute()
                    )
                    if dup_res and dup_res.data:
                        errors['option_name'] = f"해당 상품에 이미 동일한 옵션('{option_name}')이 존재합니다."
                except Exception as dup_err:
                    logger.error("옵션명 중복 확인 실패: %s", dup_err)

        # 6. SKU 입력 시 기존 SKU 중복 확인
        if sku:
            try:
                dup_sku_res = (
                    admin_supabase.table('product_options')
                    .select('id')
                    .eq('sku', sku)
                    .maybe_single()
                    .execute()
                )
                if dup_sku_res and dup_sku_res.data:
                    errors['sku'] = f"이미 사용 중인 SKU 코드('{sku}')입니다."
            except Exception as sku_err:
                logger.error("SKU 중복 확인 실패: %s", sku_err)

        # 검증 실패 시 입력값 유지 후 재렌더링
        if errors:
            return render_template(
                'admin/inventory_form.html',
                active_menu='inventory',
                products=products,
                form_data=request.form,
                errors=errors
            )

        # 7. product_options 테이블에 INSERT
        insert_payload = {
            'product_id': product_id,
            'option_name': option_name,
            'additional_price': additional_price,
            'stock_quantity': stock_quantity,
            'sku': sku or None
        }

        try:
            insert_res = admin_supabase.table('product_options').insert(insert_payload).execute()
            if not insert_res or not insert_res.data:
                raise Exception("옵션 등록 결과가 올바르지 않습니다.")

            flash(f"상품 옵션 '{option_name}' (재고 {stock_quantity}개)이(가) 성공적으로 등록되었습니다.", 'success')
            return redirect(url_for('admin.inventory_list'))

        except Exception as insert_err:
            logger.error("상품 옵션 등록 실패: %s", insert_err, exc_info=True)
            flash('옵션 등록 중 오류가 발생했습니다. 다시 시도해 주세요.', 'danger')
            return render_template(
                'admin/inventory_form.html',
                active_menu='inventory',
                products=products,
                form_data=request.form,
                errors={'general': '옵션 저장 중 오류가 발생했습니다.'}
            )

    # GET 요청: 빈 폼 렌더링
    return render_template(
        'admin/inventory_form.html',
        active_menu='inventory',
        products=products,
        form_data={'additional_price': '0', 'stock_quantity': '0'},
        errors={}
    )

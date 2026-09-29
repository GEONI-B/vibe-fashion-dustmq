# app/routes/auth.py - 인증(로그인, 회원가입, 이메일 인증, 비밀번호 찾기) 라우트 모듈
"""
Supabase Auth 기반 사용자 인증 모듈입니다.
회원가입, 이메일/비밀번호 로그인, 이메일 인증, 비밀번호 재설정 및 세션 관리를 처리합니다.
"""

import os
import re
import logging
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv
from supabase import create_client, Client

# 로깅 설정
logger = logging.getLogger(__name__)

# auth 블루프린트 생성
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

load_dotenv()

# 한국어 에러 및 성공 메시지 매핑
ERROR_MESSAGES = {
    'email_not_confirmed': '이메일 인증이 완료되지 않았습니다. 메일함에서 인증 링크를 클릭해 주세요.',
    'invalid_credentials': '이메일 또는 비밀번호가 올바르지 않습니다.',
    'already_registered': '이미 가입된 이메일 주소입니다. 로그인해 주세요.',
    'invalid_request': '모든 필수 입력 항목을 올바르게 입력해 주세요.',
    'password_mismatch': '비밀번호와 비밀번호 확인이 일치하지 않습니다.',
    'password_too_short': '비밀번호는 최소 8자 이상이어야 합니다.',
    'password_needs_digit': '비밀번호에 숫자를 1개 이상 포함해야 합니다.',
    'password_needs_special': '비밀번호에 특수문자를 1개 이상 포함해야 합니다.',
    'password_same_as_email': '이메일 주소와 동일한 비밀번호는 사용할 수 없습니다.',
    'invalid_token': '유효하지 않거나 만료된 인증 링크입니다. 다시 시도해 주세요.',
    'login_required': '로그인이 필요한 서비스입니다.',
    'rate_limit': '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.',
    'server_error': '요청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
    'session_expired': '인증 세션이 만료되었습니다. 다시 비밀번호 재설정을 요청해 주세요.'
}

SUCCESS_MESSAGES = {
    'signup_success': '회원가입이 완료되었습니다.',
    'email_confirmed': '이메일 인증이 완료되었습니다! VIBE FASHION에 오신 것을 환영합니다.',
    'reset_mail_sent': '비밀번호 재설정 링크를 입력하신 이메일로 전송했습니다.',
    'password_reset_success': '비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 로그인해 주세요.',
    'logged_out': '성공적으로 로그아웃되었습니다.',
}


def validate_password_policy(password: str, email: str = "") -> str | None:
    """
    비밀번호 정책 검증 함수:
    - 최소 8자 이상
    - 숫자 1개 이상 포함
    - 특수문자 1개 이상 포함
    - 이메일 주소와 동일한 비밀번호 금지 (대소문자 무시)
    통과 시 None 반환, 위반 시 에러 키 반환.
    """
    if len(password) < 8:
        return 'password_too_short'
    if not re.search(r'\d', password):
        return 'password_needs_digit'
    if not re.search(r'[^A-Za-z0-9]', password):
        return 'password_needs_special'
    if email and password.lower() == email.strip().lower():
        return 'password_same_as_email'
    return None


def get_supabase_client(use_service_role: bool = False) -> Client:
    """
    환경 변수로부터 Supabase 클라이언트를 초기화하여 반환합니다.
    use_service_role=True인 경우 관리자 권한 클라이언트를 반환합니다.
    """
    supabase_url = os.getenv('SUPABASE_URL')
    anon_key = os.getenv('SUPABASE_ANON_KEY')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')

    key = service_key if (use_service_role and service_key) else anon_key

    if not supabase_url or not key:
        raise ValueError("SUPABASE_URL 또는 관련 KEY 환경 변수가 설정되지 않았습니다.")

    return create_client(supabase_url, key)


def login_required(f):
    """
    Flask 세션에서 user_id를 확인하여 비로그인 사용자의 접근을 차단하는 데코레이터입니다.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id') or (
            session.get('user', {}).get('id') if isinstance(session.get('user'), dict) else None
        )
        if not user_id:
            return redirect(url_for('auth.login', next=request.url, error='login_required'))
        return f(*args, **kwargs)
    return decorated_function


# ------------------------------------------------------------------------------
# [1] GET/POST /auth/login - 로그인 폼 및 처리
# ------------------------------------------------------------------------------
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    로그인 페이지 렌더링 및 로그인 처리
    이메일 미인증 시 error=email_not_confirmed 로 리다이렉트
    """
    # 이미 로그인된 상태라면 메인으로 리다이렉트
    if session.get('user_id') or session.get('user'):
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        next_url = request.args.get('next')

        if not email or not password:
            return redirect(url_for('auth.login', error='invalid_request', next=next_url))

        try:
            supabase = get_supabase_client()
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            user = response.user
            auth_session = response.session

            if user:
                # profiles 테이블에서 닉네임 및 회원 등급 조회
                profile_name = (
                    user.user_metadata.get('name')
                    or user.user_metadata.get('full_name')
                    or (user.email.split('@')[0] if user.email else '회원')
                )
                user_grade = 'BRONZE'
                try:
                    prof_res = supabase.table('profiles').select('name, grade').eq('id', user.id).maybe_single().execute()
                    if prof_res and prof_res.data:
                        profile_name = prof_res.data.get('name') or profile_name
                        user_grade = prof_res.data.get('grade') or user_grade
                except Exception as p_err:
                    logger.warning("프로필 조회 생략: %s", p_err)

                # Flask 세션에 사용자 정보 저장
                session['user_id'] = user.id
                session['user'] = {
                    'id': user.id,
                    'email': user.email,
                    'name': profile_name,
                    'grade': user_grade
                }
                if auth_session:
                    session['access_token'] = auth_session.access_token

                flash(f'{profile_name}님, 환영합니다!', 'success')
                return redirect(next_url or url_for('main.index'))

        except Exception as e:
            error_msg = str(e).lower()
            logger.error("로그인 실패: %s", e)

            # 이메일 미인증 상태 확인
            if 'email not confirmed' in error_msg or 'email_not_confirmed' in error_msg:
                return redirect(url_for('auth.login', error='email_not_confirmed', next=next_url))
            elif 'invalid' in error_msg or 'credentials' in error_msg or 'grant' in error_msg:
                return redirect(url_for('auth.login', error='invalid_credentials', next=next_url))
            else:
                return redirect(url_for('auth.login', error='server_error', next=next_url))

    # GET 요청: URL 파라미터 에러/성공 메시지 파싱
    error_key = request.args.get('error')
    msg_key = request.args.get('msg')
    error_message = ERROR_MESSAGES.get(error_key, error_key) if error_key else None
    success_message = SUCCESS_MESSAGES.get(msg_key, msg_key) if msg_key else None

    return render_template(
        'login.html',
        error_message=error_message,
        success_message=success_message
    )


# ------------------------------------------------------------------------------
# [2] GET/POST /auth/signup - 회원가입 폼 및 처리
# ------------------------------------------------------------------------------
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    회원가입 폼 제공 및 신규 회원 가입 처리
    가입 성공 시 /auth/signup-complete 로 리다이렉트
    """
    if session.get('user_id') or session.get('user'):
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()

        # 유효성 검사
        if not name or not email or not password or not password_confirm:
            return redirect(url_for('auth.signup', error='invalid_request'))
        
        # 비밀번호 정책 검증 (8자 이상, 숫자 1개 이상, 특수문자 1개 이상, 이메일과 동일 금지)
        pwd_error = validate_password_policy(password, email=email)
        if pwd_error:
            return redirect(url_for('auth.signup', error=pwd_error))

        if password != password_confirm:
            return redirect(url_for('auth.signup', error='password_mismatch'))

        site_url = os.getenv("SITE_URL", "http://localhost:5000").rstrip("/")
        email_redirect_to = f"{site_url}/auth/confirm"

        try:
            supabase = get_supabase_client()
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "email_redirect_to": email_redirect_to,
                    "data": {
                        "name": name,
                        "full_name": name
                    }
                }
            })

            user = response.user
            # 이미 가입된 사용자인 경우 identities가 빈 배열로 반환됨
            if user and hasattr(user, 'identities') and user.identities == []:
                return redirect(url_for('auth.signup', error='already_registered'))

            return redirect(url_for('auth.signup_complete', email=email))

        except Exception as e:
            error_msg = str(e).lower()
            logger.error("회원가입 실패: %s", e)
            if 'already' in error_msg:
                return redirect(url_for('auth.signup', error='already_registered'))
            elif 'rate limit' in error_msg:
                return redirect(url_for('auth.signup', error='rate_limit'))
            else:
                return redirect(url_for('auth.signup', error='server_error'))

    error_key = request.args.get('error')
    error_message = ERROR_MESSAGES.get(error_key, error_key) if error_key else None

    return render_template('signup.html', error_message=error_message)


# ------------------------------------------------------------------------------
# [3] GET /auth/signup-complete - 회원가입 완료 및 이메일 인증 안내
# ------------------------------------------------------------------------------
@auth_bp.route('/signup-complete', methods=['GET'])
def signup_complete():
    """
    회원가입 완료 후 이메일 인증 안내 화면 표시
    """
    email = request.args.get('email', '')
    return render_template('signup_complete.html', email=email)


# ------------------------------------------------------------------------------
# [4] GET /auth/confirm - 이메일 인증 링크 클릭 처리
# ------------------------------------------------------------------------------
@auth_bp.route('/confirm', methods=['GET'])
def confirm():
    """
    이메일 인증 링크 클릭 시 토큰/코드 검증 처리
    verify_otp 호출 → 성공 시 Flask session 저장 → /mypage 로 이동
    """
    token_hash = request.args.get('token_hash')
    otp_type = request.args.get('type', 'signup')
    code = request.args.get('code')
    token = request.args.get('token')
    email = request.args.get('email')

    if not token_hash and not code and not (token and email):
        logger.warning("이메일 인증 매개변수 누락: token_hash, code, token")
        return redirect(url_for('auth.login', error='invalid_token'))

    try:
        supabase = get_supabase_client()
        auth_response = None

        if token_hash:
            auth_response = supabase.auth.verify_otp({
                "token_hash": token_hash,
                "type": otp_type
            })
        elif code:
            auth_response = supabase.auth.exchange_code_for_session({
                "auth_code": code
            })
        elif token and email:
            auth_response = supabase.auth.verify_otp({
                "token": token,
                "email": email,
                "type": otp_type
            })

        if not auth_response or not auth_response.user:
            return redirect(url_for('auth.login', error='invalid_token'))

        user = auth_response.user
        auth_session = auth_response.session

        # profiles 테이블 정보 확인
        profile_name = (
            user.user_metadata.get('name')
            or user.user_metadata.get('full_name')
            or (user.email.split('@')[0] if user.email else '회원')
        )
        user_grade = 'BRONZE'
        try:
            prof_res = supabase.table('profiles').select('name, grade').eq('id', user.id).maybe_single().execute()
            if prof_res and prof_res.data:
                profile_name = prof_res.data.get('name') or profile_name
                user_grade = prof_res.data.get('grade') or user_grade
        except Exception as p_err:
            logger.warning("이메일 인증 후 프로필 조회 생략: %s", p_err)

        # Flask 세션에 사용자 정보 저장
        session['user_id'] = user.id
        session['user'] = {
            'id': user.id,
            'email': user.email,
            'name': profile_name,
            'grade': user_grade
        }
        if auth_session:
            session['access_token'] = auth_session.access_token

        flash('이메일 인증이 성공적으로 완료되었습니다!', 'success')
        return redirect('/mypage')

    except Exception as e:
        logger.error("이메일 인증(confirm) 처리 오류: %s", e)
        return redirect(url_for('auth.login', error='invalid_token'))


# ------------------------------------------------------------------------------
# [5] GET/POST /auth/forgot-password - 비밀번호 재설정 메일 발송
# ------------------------------------------------------------------------------
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
    비밀번호 찾기(재설정 메일 발송) 폼 제공 및 메일 전송 처리
    """
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            return redirect(url_for('auth.forgot_password', error='invalid_request'))

        site_url = os.getenv("SITE_URL", "http://localhost:5000").rstrip("/")
        redirect_to = f"{site_url}/auth/reset-password"

        try:
            supabase = get_supabase_client()
            supabase.auth.reset_password_for_email(email, options={"redirect_to": redirect_to})
            return redirect(url_for('auth.forgot_password', msg='reset_mail_sent', email=email))
        except Exception as e:
            logger.error("비밀번호 재설정 메일 발송 오류: %s", e)
            return redirect(url_for('auth.forgot_password', error='server_error'))

    error_key = request.args.get('error')
    msg_key = request.args.get('msg')
    error_message = ERROR_MESSAGES.get(error_key, error_key) if error_key else None
    success_message = SUCCESS_MESSAGES.get(msg_key, msg_key) if msg_key else None
    email = request.args.get('email', '')

    return render_template(
        'forgot_password.html',
        error_message=error_message,
        success_message=success_message,
        email=email
    )


# ------------------------------------------------------------------------------
# [6] GET/POST /auth/reset-password - 새 비밀번호 설정
# ------------------------------------------------------------------------------
@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """
    새 비밀번호 입력 폼 제공 및 비밀번호 업데이트 처리
    """
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        token_hash = request.form.get('token_hash', '').strip()
        access_token = request.form.get('access_token', '').strip() or session.get('recovery_access_token')
        refresh_token = request.form.get('refresh_token', '').strip() or session.get('recovery_refresh_token', '')

        if not password or not password_confirm:
            return redirect(url_for('auth.reset_password', error='invalid_request', token_hash=token_hash))
        
        # 비밀번호 정책 검증 (8자 이상, 숫자 1개 이상, 특수문자 1개 이상)
        pwd_error = validate_password_policy(password)
        if pwd_error:
            return redirect(url_for('auth.reset_password', error=pwd_error, token_hash=token_hash))

        if password != password_confirm:
            return redirect(url_for('auth.reset_password', error='password_mismatch', token_hash=token_hash))

        try:
            supabase = get_supabase_client()

            # token_hash가 있는 경우 1차로 recovery 세션 검증 시도
            if token_hash and not access_token:
                try:
                    auth_res = supabase.auth.verify_otp({
                        "token_hash": token_hash,
                        "type": "recovery"
                    })
                    if auth_res.session:
                        access_token = auth_res.session.access_token
                        refresh_token = auth_res.session.refresh_token
                except Exception as v_err:
                    logger.warning("POST recovery verify_otp 오류: %s", v_err)

            if access_token:
                try:
                    supabase.auth.set_session(access_token, refresh_token or "")
                except Exception as s_err:
                    logger.warning("set_session 오류: %s", s_err)
                supabase.auth.update_user({"password": password})
            elif session.get('user_id'):
                if session.get('access_token'):
                    try:
                        supabase.auth.set_session(session['access_token'], "")
                    except Exception:
                        pass
                supabase.auth.update_user({"password": password})
            else:
                return redirect(url_for('auth.reset_password', error='session_expired'))

            # 세션에서 recovery 임시 토큰 정리
            session.pop('recovery_access_token', None)
            session.pop('recovery_refresh_token', None)

            return redirect(url_for('auth.login', msg='password_reset_success'))

        except Exception as e:
            logger.error("새 비밀번호 설정 실패: %s", e)
            return redirect(url_for('auth.reset_password', error='server_error', token_hash=token_hash))

    # GET 요청: URL 파라미터로 토큰 확인 및 세션 저장
    token_hash = request.args.get('token_hash', '')
    code = request.args.get('code', '')
    otp_type = request.args.get('type', 'recovery')

    if token_hash:
        try:
            supabase = get_supabase_client()
            auth_res = supabase.auth.verify_otp({
                "token_hash": token_hash,
                "type": otp_type
            })
            if auth_res.session:
                session['recovery_access_token'] = auth_res.session.access_token
                session['recovery_refresh_token'] = auth_res.session.refresh_token
        except Exception as v_err:
            logger.warning("GET recovery verify_otp 오류: %s", v_err)
    elif code:
        try:
            supabase = get_supabase_client()
            auth_res = supabase.auth.exchange_code_for_session({
                "auth_code": code
            })
            if auth_res.session:
                session['recovery_access_token'] = auth_res.session.access_token
                session['recovery_refresh_token'] = auth_res.session.refresh_token
        except Exception as c_err:
            logger.warning("GET recovery code exchange 오류: %s", c_err)

    error_key = request.args.get('error')
    msg_key = request.args.get('msg')
    error_message = ERROR_MESSAGES.get(error_key, error_key) if error_key else None
    success_message = SUCCESS_MESSAGES.get(msg_key, msg_key) if msg_key else None

    return render_template(
        'reset_password.html',
        error_message=error_message,
        success_message=success_message,
        token_hash=token_hash
    )


# ------------------------------------------------------------------------------
# 기타 인증 관리: 로그아웃 및 회원탈퇴
# ------------------------------------------------------------------------------
@auth_bp.route('/logout')
def logout():
    """
    로그아웃 처리
    """
    try:
        supabase = get_supabase_client()
        supabase.auth.sign_out()
    except Exception as e:
        logger.warning("Supabase sign_out 경고: %s", e)

    session.pop('user_id', None)
    session.pop('user', None)
    session.pop('access_token', None)
    session.pop('recovery_access_token', None)
    session.pop('recovery_refresh_token', None)

    return redirect(url_for('auth.login', msg='logged_out'))


@auth_bp.route('/withdraw', methods=['POST'])
@login_required
def withdraw():
    """
    회원 탈퇴 처리
    로그인된 사용자의 계정을 삭제(auth.admin.delete_user 및 세션 정리)합니다.
    """
    user_id = session.get('user_id') or session.get('user', {}).get('id')
    user_name = session.get('user', {}).get('name', '회원')

    try:
        service_key = os.getenv('SUPABASE_SERVICE_KEY')
        supabase_admin = get_supabase_client(use_service_role=bool(service_key))

        try:
            supabase_admin.table('profiles').delete().eq('id', user_id).execute()
        except Exception as p_err:
            logger.warning("회원탈퇴 profiles 레코드 삭제 경고: %s", p_err)

        try:
            supabase_admin.auth.admin.delete_user(user_id)
        except Exception as a_err:
            logger.warning("auth.admin.delete_user 실패: %s", a_err)

        session.clear()
        flash(f'{user_name}님, 회원탈퇴가 완료되었습니다. 이용해 주셔서 감사합니다.', 'info')
        return redirect(url_for('main.index'))

    except Exception as e:
        logger.error("회원탈퇴 처리 중 오류 발생: %s", e, exc_info=True)
        flash('회원탈퇴 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.', 'danger')
        return redirect(url_for('main.index'))



# app/routes/auth.py - 인증(로그인, 회원가입, 로그아웃) 라우트 모듈
"""
Supabase Auth를 기반으로 동작하는 사용자 인증 모듈입니다.
회원가입, 이메일/비밀번호 로그인, 로그아웃 및 사용자 세션 관리를 처리합니다.
"""

import os
import sys
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv
from supabase import create_client, Client

# 로깅 설정
logger = logging.getLogger(__name__)

# auth 블루프린트 생성
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

load_dotenv()


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


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    로그인 페이지 렌더링 및 로그인 처리
    """
    # 이미 로그인된 상태라면 메인으로 리다이렉트
    if session.get('user'):
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('이메일과 비밀번호를 모두 입력해 주세요.', 'danger')
            return render_template('login.html', email=email)

        try:
            supabase = get_supabase_client()
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            user = response.user
            auth_session = response.session

            if user:
                # profiles 테이블에서 추가 정보 조회 시도
                profile_name = user.user_metadata.get('name') or user.user_metadata.get('full_name') or email.split('@')[0]
                user_grade = 'BRONZE'
                try:
                    prof_res = supabase.table('profiles').select('name, grade').eq('id', user.id).maybe_single().execute()
                    if prof_res and prof_res.data:
                        profile_name = prof_res.data.get('name') or profile_name
                        user_grade = prof_res.data.get('grade') or user_grade
                except Exception as p_err:
                    logger.warning("프로필 추가 조회 생략: %s", p_err)

                # Flask 세션에 사용자 정보 저장
                session['user'] = {
                    'id': user.id,
                    'email': user.email,
                    'name': profile_name,
                    'grade': user_grade
                }
                if auth_session:
                    session['access_token'] = auth_session.access_token

                flash(f'{profile_name}님, 환영합니다!', 'success')
                next_url = request.args.get('next')
                return redirect(next_url or url_for('main.index'))

        except Exception as e:
            error_message = str(e)
            logger.error("로그인 실패: %s", error_message)
            if 'Invalid login credentials' in error_message or 'invalid_grant' in error_message:
                flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'danger')
            elif 'Email not confirmed' in error_message:
                flash('이메일 인증이 완료되지 않았습니다. 메일함을 확인해 주세요.', 'warning')
            else:
                flash('로그인 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.', 'danger')

    return render_template('login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    회원가입 페이지 렌더링 및 신규 사용자 등록
    """
    if session.get('user'):
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()

        # 유효성 검사
        if not name or not email or not password or not password_confirm:
            flash('모든 필드를 입력해 주세요.', 'danger')
            return render_template('signup.html', name=name, email=email)

        if len(password) < 6:
            flash('비밀번호는 최소 6자 이상이어야 합니다.', 'danger')
            return render_template('signup.html', name=name, email=email)

        if password != password_confirm:
            flash('비밀번호와 비밀번호 확인이 일치하지 않습니다.', 'danger')
            return render_template('signup.html', name=name, email=email)

        try:
            # 1. 개발 및 테스트 환경에서 Supabase 기본 이메일 발송 제한(Email rate limit)을 우회하고
            #    즉시 로그인이 가능하도록 Service Key가 존재하면 admin API로 가입 및 이메일 자동 확인 처리
            service_key = os.getenv('SUPABASE_SERVICE_KEY')
            user = None
            auth_session = None

            if service_key:
                try:
                    admin_client = get_supabase_client(use_service_role=True)
                    admin_res = admin_client.auth.admin.create_user({
                        "email": email,
                        "password": password,
                        "email_confirm": True,
                        "user_metadata": {
                            "name": name,
                            "full_name": name
                        }
                    })
                    user = admin_res.user

                    # 가입 즉시 클라이언트 로그인 세션 획득
                    client = get_supabase_client(use_service_role=False)
                    sign_in_res = client.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })
                    auth_session = sign_in_res.session
                    user = sign_in_res.user
                except Exception as admin_err:
                    admin_msg = str(admin_err)
                    if 'already registered' in admin_msg or 'User already registered' in admin_msg:
                        flash('이미 가입된 이메일 주소입니다.', 'danger')
                        return render_template('signup.html', name=name, email=email)
                    logger.warning("Admin create_user 실패, 일반 sign_up으로 대체: %s", admin_msg)
                    user = None

            # 2. 일반 sign_up 폴백
            if not user:
                supabase = get_supabase_client(use_service_role=False)
                response = supabase.auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": {
                        "data": {
                            "name": name,
                            "full_name": name
                        }
                    }
                })
                user = response.user
                auth_session = response.session

            if user:
                # profiles 테이블 생성 대기 및 정보 조회
                user_grade = 'BRONZE'
                try:
                    db_client = get_supabase_client(use_service_role=bool(service_key))
                    prof_res = db_client.table('profiles').select('grade').eq('id', user.id).maybe_single().execute()
                    if prof_res and prof_res.data:
                        user_grade = prof_res.data.get('grade') or 'BRONZE'
                except Exception as p_err:
                    logger.warning("가입 후 프로필 등급 조회 생략: %s", p_err)

                session['user'] = {
                    'id': user.id,
                    'email': user.email,
                    'name': name,
                    'grade': user_grade
                }
                if auth_session:
                    session['access_token'] = auth_session.access_token

                flash(f'{name}님, 회원가입이 완료되어 자동으로 로그인되었습니다!', 'success')
                return redirect(url_for('main.index'))

        except Exception as e:
            error_message = str(e)
            logger.error("회원가입 실패: %s", error_message)
            if 'already registered' in error_message or 'User already registered' in error_message:
                flash('이미 가입된 이메일 주소입니다.', 'danger')
            elif 'rate limit' in error_message.lower():
                flash('요청 횟수 제한을 초과했습니다. 잠시 후 다시 시도해 주세요.', 'danger')
            else:
                flash(f'회원가입 실패: {error_message}', 'danger')

    return render_template('signup.html')


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

    session.pop('user', None)
    session.pop('access_token', None)
    flash('성공적으로 로그아웃되었습니다.', 'info')
    return redirect(url_for('main.index'))

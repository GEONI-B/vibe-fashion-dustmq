# app/__init__.py - VIBE-FASHION 앱 팩토리 파일
from flask import Flask
from dotenv import load_dotenv
import os

"""
"VIBE FASHION" 패션 쇼핑몰 웹앱
Flask 애플리케이션 팩토리(Application Factory) 패턴을 적용한 초기화 모듈입니다.
"""

def create_app():
    """
    Flask 애플리케이션 인스턴스를 생성하고 환경을 설정하는 팩토리 함수입니다.
    초보자도 이해하기 쉽도록 단계별로 구성되어 있습니다.
    """
    # 1. .env 파일로부터 환경 변수 로드
    load_dotenv()

    # 2. Flask 애플리케이션 인스턴스 생성
    app = Flask(__name__)

    # 3. 애플리케이션 시크릿 키 설정
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'vibe-fashion-secret-key-2026')

    # 4. routes 블루프린트 등록
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    return app

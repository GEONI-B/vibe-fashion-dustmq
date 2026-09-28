# run.py - VIBE FASHION 애플리케이션 실행 파일
"""
Flask 애플리케이션 팩토리 패턴을 통해 생성된 앱 인스턴스를 실행하는 진입점 파일입니다.
"""

from app import create_app

# 애플리케이션 팩토리 함수 호출
app = create_app()

if __name__ == '__main__':
    print("==========================================")
    print(" [VIBE FASHION] 패션 쇼핑몰 서버 시작")
    print(" 접속 주소: http://127.0.0.1:5000")
    print("==========================================")
    # 로컬 개발 서버 실행
    app.run(host='127.0.0.1', port=5000, debug=True)

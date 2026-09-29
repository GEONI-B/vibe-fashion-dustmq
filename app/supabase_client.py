# app/supabase_client.py - Supabase 클라이언트 공통 모듈
"""
Supabase 클라이언트 생성 및 관리를 담당하는 공통 유틸리티 모듈입니다.
중복 생성을 방지하고 일관된 클라이언트 인터페이스를 제공합니다.
"""

import os
from supabase import create_client, Client

_client: Client | None = None
_admin_client: Client | None = None


def get_supabase_client(use_service_role: bool = False) -> Client:
    """
    환경 변수로부터 Supabase 클라이언트를 초기화하여 반환합니다.
    use_service_role=True인 경우 관리자 권한 클라이언트를 반환합니다.
    """
    global _client, _admin_client

    supabase_url = os.getenv('SUPABASE_URL')
    anon_key = os.getenv('SUPABASE_ANON_KEY')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')

    if use_service_role:
        if not service_key:
            raise ValueError("SUPABASE_SERVICE_KEY 환경 변수가 설정되지 않았습니다.")
        if _admin_client is None:
            _admin_client = create_client(supabase_url, service_key)
        return _admin_client

    if not supabase_url or not anon_key:
        raise ValueError("SUPABASE_URL 또는 SUPABASE_ANON_KEY 환경 변수가 설정되지 않았습니다.")

    if _client is None:
        _client = create_client(supabase_url, anon_key)
    return _client

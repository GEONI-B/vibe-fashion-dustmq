/**
 * VIBE FASHION - 클라이언트 자바스크립트
 * 초보자가 이해하기 쉬운 한국어 주석과 깔끔한 이벤트 핸들러
 */

/**
 * 장바구니 담기 함수
 * 상품 카드에서 "장바구니 담기" 버튼 클릭 시 서버 API를 호출하여 세션 장바구니에 상품을 추가합니다.
 * @param {string} productId - 장바구니에 담을 상품 고유 UUID
 * @param {string} productName - 장바구니에 담을 상품명
 */
function addToCart(productId, productName) {
    fetch('/api/cart/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            product_id: productId,
            quantity: 1
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // 상단 네비게이션 바의 장바구니 뱃지 숫자 갱신
            updateCartBadge(data.cart_count);

            // 토스트 알림 메시지 설정 및 표시
            const toastElement = document.getElementById('cartToast');
            const toastMessage = document.getElementById('toastMessage');

            if (toastElement && toastMessage) {
                toastMessage.innerHTML = `<strong>${productName}</strong> 상품이 장바구니에 추가되었습니다!`;
                const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
                toast.show();
            }
        } else {
            alert(data.message || '장바구니 담기에 실패했습니다.');
        }
    })
    .catch(err => {
        console.error('장바구니 담기 에러:', err);
    });
}

/**
 * 상단 네비게이션 바의 장바구니 뱃지 수량 갱신 함수
 */
function updateCartBadge(count) {
    const cartCountBadge = document.getElementById('cartCount');
    if (cartCountBadge) {
        cartCountBadge.textContent = count;
    }
}

/**
 * 페이지 로드 시 현재 장바구니 수량 동기화
 */
function loadCartCount() {
    fetch('/api/cart/count')
        .then(res => res.json())
        .then(data => {
            if (data && typeof data.cart_count === 'number') {
                updateCartBadge(data.cart_count);
            }
        })
        .catch(err => console.error('장바구니 카운트 로드 실패:', err));
}

/**
 * 로그인 필요 모달 팝업 표시 함수
 * @param {string} customMessage - 커스텀 알림 문구 (기본: '로그인해야 합니다')
 */
function showLoginModal(customMessage) {
    const message = customMessage || '로그인해야 합니다';
    const textEl = document.getElementById('loginAlertModalText');
    if (textEl) {
        textEl.textContent = message;
    }

    const modalEl = document.getElementById('loginAlertModal');
    if (modalEl && typeof bootstrap !== 'undefined') {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    } else {
        alert(message);
    }
}

/**
 * 상단 관심 상품(하트 아이콘) 네비게이션 클릭 처리
 * 로그인하지 않은 경우 "로그인해야 이용 가능한 페이지입니다" 모달 표시
 * 로그인한 경우 /wishlist 페이지로 이동
 */
function handleWishlistNav() {
    if (!window.IS_LOGGED_IN) {
        showLoginModal('로그인해야 이용 가능한 페이지입니다');
        return;
    }
    window.location.href = '/wishlist';
}

/**
 * 관심 상품(위시리스트) 하트 토글 함수
 * 로그인하지 않은 사용자는 경고 문구를 표시하고 하트 변경을 차단합니다.
 * @param {HTMLElement} button - 클릭된 버튼 엘리먼트
 * @param {string} productName - 상품명
 */
function toggleWishlist(button, productName) {
    if (!window.IS_LOGGED_IN) {
        showLoginModal('로그인해야 합니다');
        return false;
    }

    // 서버 위시리스트 토글 API 연동 (카드의 addToCart 호출과 유사한 구조)
    const cardEl = button.closest('.product-card');
    const cartBtn = cardEl ? cardEl.querySelector('.btn-add-cart') : null;
    let productId = null;
    if (cartBtn) {
        const onclickAttr = cartBtn.getAttribute('onclick') || '';
        const match = onclickAttr.match(/addToCart\('([^']+)'/);
        if (match) {
            productId = match[1];
        }
    }

    if (productId) {
        fetch('/api/wishlist/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const icon = button.querySelector('i');
                if (data.is_added) {
                    button.classList.add('active');
                    if (icon) {
                        icon.classList.remove('bi-heart');
                        icon.classList.add('bi-heart-fill');
                    }
                    console.log(`[관심상품 등록] ${productName}`);
                } else {
                    button.classList.remove('active');
                    if (icon) {
                        icon.classList.remove('bi-heart-fill');
                        icon.classList.add('bi-heart');
                    }
                    console.log(`[관심상품 해제] ${productName}`);
                }
            } else if (data.need_login) {
                showLoginModal('로그인해야 이용 가능한 페이지입니다');
            }
        })
        .catch(err => console.error('위시리스트 토글 통신 실패:', err));
        return;
    }

    // 기본 UI 토글 fallback
    const icon = button.querySelector('i');
    button.classList.toggle('active');
    if (button.classList.contains('active')) {
        icon.classList.remove('bi-heart');
        icon.classList.add('bi-heart-fill');
        console.log(`[관심상품 등록] ${productName}`);
    } else {
        icon.classList.remove('bi-heart-fill');
        icon.classList.add('bi-heart');
        console.log(`[관심상품 해제] ${productName}`);
    }
}

/**
 * 상단 네비게이션 활성화(Active) 상태 관리 함수
 * 현재 페이지 경로 및 해시에 맞춰 해당 카테고리 폰트 색상을 변경하고, 클릭 시 즉시 활성화합니다.
 */
function initNavbarActive() {
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    if (!navLinks.length) return;

    const currentPath = window.location.pathname;
    const currentHash = window.location.hash;

    // 초기 활성화 상태 결정
    let matchedLink = null;
    navLinks.forEach(link => {
        const href = link.getAttribute('href') || '';
        // 해시가 있는 경우 우선 매칭 (예: #products, #collections)
        if (currentHash && href.includes(currentHash)) {
            matchedLink = link;
        } else if (!currentHash && !matchedLink) {
            if (href === currentPath || (currentPath === '/' && (href === '/' || href.endsWith('/')))) {
                matchedLink = link;
            }
        }
    });

    // 기본값: 홈
    if (!matchedLink && currentPath === '/') {
        matchedLink = navLinks[0];
    }

    if (matchedLink) {
        navLinks.forEach(l => l.classList.remove('active'));
        matchedLink.classList.add('active');
    }

    // 클릭 시 해당 카테고리만 활성화
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            navLinks.forEach(l => l.classList.remove('active'));
            this.classList.add('active');
        });
    });
}

/**
 * 사이트 접속 시 "준비 중인 사이트" 알림 모달 팝업 표시
 */
function showSiteUnderConstructionModal() {
    const modalEl = document.getElementById('siteUnderConstructionModal');
    if (modalEl && typeof bootstrap !== 'undefined') {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    }
}

// 문서 로드 완료 시 초기화 작업
document.addEventListener('DOMContentLoaded', () => {
    loadCartCount();
    initNavbarActive();
    showSiteUnderConstructionModal();
    console.log('VIBE FASHION 웹앱이 성공적으로 로드되었습니다.');
});

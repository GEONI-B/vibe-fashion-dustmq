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
function csrfHeaders(headers = {}) {
    const token = document.querySelector('meta[name="csrf-token"]')?.content;
    return token ? { ...headers, 'X-CSRFToken': token } : headers;
}

function addToCart(productId, productName) {
    fetch('/api/cart/add', {
        method: 'POST',
        headers: csrfHeaders({
            'Content-Type': 'application/json'
        }),
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
            const toastProductName = document.getElementById('toastProductName');

            if (toastElement && toastProductName) {
                toastProductName.textContent = productName;
                const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
                toast.show();
            }
        } else {
            showAppAlert(data.message || '장바구니 담기에 실패했습니다.');
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
    showAppAlert(message);
}

/**
 * 테마에 맞는 공통 안내 및 확인 모달을 표시합니다.
 * @param {string} message - 사용자에게 표시할 메시지
 * @param {{confirm?: boolean, confirmLabel?: string}} options - 확인 버튼 표시 옵션
 * @returns {Promise<boolean>} 확인을 선택했는지 여부
 */
function showAppDialog(message, options = {}) {
    const modalEl = document.getElementById('appDialogModal');
    if (!modalEl || typeof bootstrap === 'undefined') {
        console.error(message);
        return Promise.resolve(false);
    }

    const isConfirm = options.confirm === true;
    const titleEl = document.getElementById('appDialogTitle');
    const messageEl = document.getElementById('appDialogMessage');
    const iconEl = document.getElementById('appDialogIcon');
    const confirmButton = document.getElementById('appDialogConfirm');
    const cancelButton = document.getElementById('appDialogCancel');

    titleEl.textContent = isConfirm ? '확인해 주세요' : '안내';
    messageEl.textContent = message;
    iconEl.className = `bi ${isConfirm ? 'bi-question-circle-fill' : 'bi-info-circle-fill'}`;
    confirmButton.textContent = options.confirmLabel || '확인';
    cancelButton.classList.toggle('d-none', !isConfirm);

    return new Promise(resolve => {
        let confirmed = false;
        const onConfirm = () => {
            confirmed = true;
        };
        const onHidden = () => {
            confirmButton.removeEventListener('click', onConfirm);
            resolve(confirmed);
        };

        confirmButton.addEventListener('click', onConfirm);
        modalEl.addEventListener('hidden.bs.modal', onHidden, { once: true });
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    });
}

function showAppAlert(message) {
    return showAppDialog(message);
}

function showAppConfirm(message, confirmLabel = '확인') {
    return showAppDialog(message, { confirm: true, confirmLabel });
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

    const productId = button.dataset.productId;
    if (!productId) return false;

    fetch('/api/wishlist/toggle', {
        method: 'POST',
        headers: csrfHeaders({ 'Content-Type': 'application/json' }),
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
}

function removeWishlistItem(productId) {
    fetch('/api/wishlist/toggle', {
        method: 'POST',
        headers: csrfHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ product_id: productId })
    })
    .then(res => res.json())
    .then(data => {
        if (!data.success) return;

        const item = document.getElementById(`wishlist-col-${productId}`);
        if (item) item.remove();
        if (!document.querySelector('[id^="wishlist-col-"]')) location.reload();
    })
    .catch(err => console.error('위시리스트 삭제 에러:', err));
}

function initProductActions() {
    document.addEventListener('click', event => {
        const button = event.target.closest('[data-product-action]');
        if (!button) return;

        const { productAction, productId, productName } = button.dataset;
        if (productAction === 'add-to-cart') {
            addToCart(productId, productName);
        } else if (productAction === 'toggle-wishlist') {
            toggleWishlist(button, productName);
        } else if (productAction === 'remove-wishlist') {
            removeWishlistItem(productId);
        }
    });
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

/**
 * 비밀번호 표시/숨김(눈 아이콘) 토글 기능 초기화
 * input-group 내의 .password-toggle-btn 클릭 시 input의 type을 password <-> text로 전환합니다.
 */
function initPasswordToggle() {
    const toggleButtons = document.querySelectorAll('.password-toggle-btn');
    toggleButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const group = this.closest('.input-group');
            if (!group) return;
            const input = group.querySelector('input');
            const icon = this.querySelector('i');
            if (!input) return;

            if (input.type === 'password') {
                input.type = 'text';
                if (icon) {
                    icon.classList.remove('bi-eye');
                    icon.classList.add('bi-eye-slash');
                }
                this.setAttribute('title', '비밀번호 숨기기');
                this.setAttribute('aria-label', '비밀번호 숨기기');
            } else {
                input.type = 'password';
                if (icon) {
                    icon.classList.remove('bi-eye-slash');
                    icon.classList.add('bi-eye');
                }
                this.setAttribute('title', '비밀번호 보기');
                this.setAttribute('aria-label', '비밀번호 보기');
            }
        });
    });
}

// 문서 로드 완료 시 초기화 작업
document.addEventListener('DOMContentLoaded', () => {
    loadCartCount();
    initProductActions();
    initNavbarActive();
    initPasswordToggle();
    showSiteUnderConstructionModal();
    console.log('VIBE FASHION 웹앱이 성공적으로 로드되었습니다.');
});

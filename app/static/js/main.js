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
 * 관심 상품(위시리스트) 하트 토글 함수
 * 하트 아이콘 클릭 시 활성화/비활성화 상태를 토글합니다.
 * @param {HTMLElement} button - 클릭된 버튼 엘리먼트
 * @param {string} productName - 상품명
 */
function toggleWishlist(button, productName) {
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

// 문서 로드 완료 시 초기화 작업
document.addEventListener('DOMContentLoaded', () => {
    loadCartCount();
    console.log('VIBE FASHION 웹앱이 성공적으로 로드되었습니다.');
});

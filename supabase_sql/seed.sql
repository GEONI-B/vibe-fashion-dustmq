-- ==============================================================================
-- VIBE-FASHION 쇼핑몰 초기 시드 데이터 (Seed Data)
-- Supabase SQL Editor에서 실행
-- ==============================================================================

DO $$
DECLARE
  v_cat_top_id BIGINT;
  v_cat_bottom_id BIGINT;
  v_cat_outer_id BIGINT;
  v_cat_dress_id BIGINT;
  v_cat_acc_id BIGINT;
  v_cat_bag_id BIGINT;
  v_cat_shoes_id BIGINT;

  v_product1_id UUID;
  v_product2_id UUID;
  v_product3_id UUID;
  v_product4_id UUID;
BEGIN
  -- ----------------------------------------------------------------------------
  -- 1. 카테고리 7개 등록 (기존 데이터가 없을 시 생성 또는 슬러그 기준 갱신)
  -- 상의(top), 하의(bottom), 아우터(outer), 원피스/세트(dress), 액세서리(acc), 가방(bag), 신발(shoes)
  -- ----------------------------------------------------------------------------
  INSERT INTO public.categories (name, slug, display_order, is_active)
  VALUES 
    ('상의', 'top', 1, TRUE),
    ('하의', 'bottom', 2, TRUE),
    ('아우터', 'outer', 3, TRUE),
    ('원피스/세트', 'dress', 4, TRUE),
    ('액세서리', 'acc', 5, TRUE),
    ('가방', 'bag', 6, TRUE),
    ('신발', 'shoes', 7, TRUE)
  ON CONFLICT (slug) DO UPDATE
  SET 
    name = EXCLUDED.name,
    display_order = EXCLUDED.display_order,
    is_active = EXCLUDED.is_active;

  -- 카테고리 ID 조회
  SELECT id INTO v_cat_top_id FROM public.categories WHERE slug = 'top';
  SELECT id INTO v_cat_bottom_id FROM public.categories WHERE slug = 'bottom';
  SELECT id INTO v_cat_outer_id FROM public.categories WHERE slug = 'outer';
  SELECT id INTO v_cat_dress_id FROM public.categories WHERE slug = 'dress';
  SELECT id INTO v_cat_acc_id FROM public.categories WHERE slug = 'acc';
  SELECT id INTO v_cat_bag_id FROM public.categories WHERE slug = 'bag';
  SELECT id INTO v_cat_shoes_id FROM public.categories WHERE slug = 'shoes';

  -- 치마 카테고리 확인/등록
  INSERT INTO public.categories (name, slug, display_order, is_active)
  VALUES ('치마/스커트', 'skirt', 8, TRUE)
  ON CONFLICT (slug) DO UPDATE
  SET name = EXCLUDED.name, display_order = EXCLUDED.display_order, is_active = EXCLUDED.is_active;

  -- ----------------------------------------------------------------------------
  -- 2. 샘플 상품 4개 등록
  -- ※ 참고: 원가 29,900원, 할인가 19,900원으로 정상 등록
  -- ----------------------------------------------------------------------------
  
  -- 상품 1: 베이직 크롭 티셔츠 (상의)
  INSERT INTO public.products (
    category_id, name, slug, description, price, sale_price, status, thumbnail_url
  )
  VALUES (
    v_cat_top_id,
    '베이직 크롭 티셔츠',
    'basic-crop-tshirt',
    '어디에나 매치하기 좋은 트렌디한 데일리 베이직 크롭 티셔츠입니다. 부드러운 코튼 소재로 편안한 착용감을 선사합니다.',
    29900,
    19900,
    'active',
    '/static/images/products/crop-tshirt.jpg'
  )
  ON CONFLICT (slug) DO UPDATE
  SET
    category_id = EXCLUDED.category_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    price = EXCLUDED.price,
    sale_price = EXCLUDED.sale_price,
    thumbnail_url = EXCLUDED.thumbnail_url
  RETURNING id INTO v_product1_id;

  -- 상품 2: 와이드 데님 팬츠 (하의)
  INSERT INTO public.products (
    category_id, name, slug, description, price, sale_price, status, thumbnail_url
  )
  VALUES (
    v_cat_bottom_id,
    '와이드 데님 팬츠',
    'wide-denim-pants',
    '멋스러운 실루엣을 연출해주는 사계절용 와이드 핏 데님 팬츠입니다.',
    39900,
    NULL,
    'active',
    '/static/images/products/wide-denim.jpg'
  )
  ON CONFLICT (slug) DO UPDATE
  SET
    category_id = EXCLUDED.category_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    price = EXCLUDED.price,
    sale_price = EXCLUDED.sale_price,
    thumbnail_url = EXCLUDED.thumbnail_url
  RETURNING id INTO v_product2_id;

  -- 상품 3: 오버핏 코튼 자켓 (아우터)
  INSERT INTO public.products (
    category_id, name, slug, description, price, sale_price, status, thumbnail_url
  )
  VALUES (
    v_cat_outer_id,
    '오버핏 코튼 자켓',
    'overfit-cotton-jacket',
    '내추럴한 워싱감과 트렌디한 오버핏으로 캐주얼하게 걸치기 좋은 코튼 자켓입니다.',
    59900,
    NULL,
    'active',
    '/static/images/products/cotton-jacket.jpg'
  )
  ON CONFLICT (slug) DO UPDATE
  SET
    category_id = EXCLUDED.category_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    price = EXCLUDED.price,
    sale_price = EXCLUDED.sale_price,
    thumbnail_url = EXCLUDED.thumbnail_url
  RETURNING id INTO v_product3_id;

  -- 상품 4: 플로럴 미디 원피스 (원피스)
  INSERT INTO public.products (
    category_id, name, slug, description, price, sale_price, status, thumbnail_url
  )
  VALUES (
    v_cat_dress_id,
    '플로럴 미디 원피스',
    'floral-midi-dress',
    '잔잔한 플라워 패턴과 페미닌한 라인이 돋보이는 플로럴 미디 원피스입니다.',
    45900,
    NULL,
    'active',
    '/static/images/products/floral-dress.jpg'
  )
  ON CONFLICT (slug) DO UPDATE
  SET
    category_id = EXCLUDED.category_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    price = EXCLUDED.price,
    sale_price = EXCLUDED.sale_price,
    thumbnail_url = EXCLUDED.thumbnail_url
  RETURNING id INTO v_product4_id;

  -- ----------------------------------------------------------------------------
  -- 3. 첫 번째 상품 옵션 9개 등록 (블랙/화이트/베이지 × S/M/L)
  -- ----------------------------------------------------------------------------
  -- 기존 옵션 재등록 시 충돌 방지를 위해 정리
  DELETE FROM public.product_options WHERE product_id = v_product1_id;

  INSERT INTO public.product_options (product_id, option_name, additional_price, stock_quantity, sku)
  VALUES
    (v_product1_id, '블랙 / S', 0, 50, 'TS-BLK-S'),
    (v_product1_id, '블랙 / M', 0, 80, 'TS-BLK-M'),
    (v_product1_id, '블랙 / L', 0, 40, 'TS-BLK-L'),
    (v_product1_id, '화이트 / S', 0, 60, 'TS-WHT-S'),
    (v_product1_id, '화이트 / M', 0, 100, 'TS-WHT-M'),
    (v_product1_id, '화이트 / L', 0, 50, 'TS-WHT-L'),
    (v_product1_id, '베이지 / S', 0, 30, 'TS-BEG-S'),
    (v_product1_id, '베이지 / M', 0, 60, 'TS-BEG-M'),
    (v_product1_id, '베이지 / L', 0, 30, 'TS-BEG-L');

  -- ----------------------------------------------------------------------------
  -- 4. 상품 추가 상세 이미지 등록 (샘플)
  -- ----------------------------------------------------------------------------
  DELETE FROM public.product_images WHERE product_id = v_product1_id;

  INSERT INTO public.product_images (product_id, image_url, display_order, is_primary)
  VALUES
    (v_product1_id, 'https://picsum.photos/seed/top-crop-detail-1/800/1000', 1, TRUE),
    (v_product1_id, 'https://picsum.photos/seed/top-crop-detail-2/800/1000', 2, FALSE),
    (v_product1_id, 'https://picsum.photos/seed/top-crop-detail-3/800/1000', 3, FALSE);

  -- ----------------------------------------------------------------------------
  -- 5. 2026 S/S 신상품 13개 등록 (바지 3개, 원피스 4개, 치마 4개, 양말 2개)
  -- ----------------------------------------------------------------------------
  -- 바지 3개
  INSERT INTO public.products (category_id, name, slug, description, price, sale_price, status, thumbnail_url)
  VALUES
    (v_cat_bottom_id, '와이드 데님 팬츠', 'new-wide-denim', '멋스러운 워싱감과 편안한 핏으로 사계절 활용하기 좋은 데일리 와이드 데님 팬츠입니다.', 39900, 34900, 'active', '/static/images/products/pants-1.jpg'),
    (v_cat_bottom_id, '핀턱 세미 와이드 슬랙스', 'new-pin-tuck-slacks', '전면 투 핀턱 디테일로 단정하면서도 모던한 실루엣을 완성하는 슬랙스입니다.', 45000, 38000, 'active', '/static/images/products/pants-2.jpg'),
    (v_cat_bottom_id, '스트릿 카고 조거 팬츠', 'new-cargo-jogger-pants', '사이드 빅 포켓과 밑단 밴딩으로 활동성과 힙한 스트릿 무드를 동시에 선사합니다.', 42000, NULL, 'active', '/static/images/products/pants-3.jpg')
  ON CONFLICT (slug) DO UPDATE
  SET category_id = EXCLUDED.category_id, name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, sale_price = EXCLUDED.sale_price, thumbnail_url = EXCLUDED.thumbnail_url;

  -- 원피스 4개
  INSERT INTO public.products (category_id, name, slug, description, price, sale_price, status, thumbnail_url)
  VALUES
    (v_cat_dress_id, '프렌치 플로럴 뷔스티에 원피스', 'new-french-floral-dress', '잔잔한 플라워 패턴과 페미닌한 뷔스티에 라인이 매력적인 롱 원피스입니다.', 49000, 39900, 'active', '/static/images/products/dress-1.jpg'),
    (v_cat_dress_id, '클래식 리넨 셔츠 롱 원피스', 'new-linen-shirt-dress', '가볍고 통기성 좋은 프리미엄 린넨 혼방 소재로 제작된 벨티드 셔츠 드레스입니다.', 58000, 49900, 'active', '/static/images/products/dress-2.jpg'),
    (v_cat_dress_id, '스퀘어넥 퍼프 미니 원피스', 'new-square-neck-mini-dress', '깔끔한 스퀘어넥과 볼륨감 있는 퍼프 소매로 단정하면서도 사랑스러운 무드를 자아냅니다.', 46000, NULL, 'active', '/static/images/products/dress-3.jpg'),
    (v_cat_dress_id, '슬림핏 니트 슬리브리스 원피스', 'new-slim-knit-dress', '부드러운 골지 니트 소재로 바디 라인을 유려하게 살려주는 맥시 원피스입니다.', 43000, 36000, 'active', '/static/images/products/dress-4.jpg')
  ON CONFLICT (slug) DO UPDATE
  SET category_id = EXCLUDED.category_id, name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, sale_price = EXCLUDED.sale_price, thumbnail_url = EXCLUDED.thumbnail_url;

  -- 치마 4개
  INSERT INTO public.products (category_id, name, slug, description, price, sale_price, status, thumbnail_url)
  VALUES
    ((SELECT id FROM public.categories WHERE slug = 'skirt'), '클래식 플리츠 테니스 스커트', 'new-pleats-tennis-skirt', '단정한 칼주름 플리츠로 경쾌하고 발랄한 룩을 연출해주는 데일리 스커트입니다.', 29900, NULL, 'active', '/static/images/products/skirt-1.jpg'),
    ((SELECT id FROM public.categories WHERE slug = 'skirt'), 'A라인 빈티지 롱 데님 스커트', 'new-aline-denim-skirt', '프론트 슬릿 디테일로 활동성을 높이고 자연스러운 워싱이 돋보이는 롱 데님 스커트입니다.', 44000, 37000, 'active', '/static/images/products/skirt-2.jpg'),
    ((SELECT id FROM public.categories WHERE slug = 'skirt'), '머메이드 슬릿 롱 스커트', 'new-mermaid-slit-skirt', '허리부터 힙라인까지 부드럽게 감싸며 밑단으로 갈수록 은은하게 퍼지는 페미닌 실루엣 스커트입니다.', 39000, NULL, 'active', '/static/images/products/skirt-3.jpg'),
    ((SELECT id FROM public.categories WHERE slug = 'skirt'), '모던 랩 체크 미디 스커트', 'new-wrap-check-skirt', '감각적인 타탄 체크 패턴과 언발란스 랩 디자인이 돋보이는 모던 미디 스커트입니다.', 41000, 35000, 'active', '/static/images/products/skirt-4.jpg')
  ON CONFLICT (slug) DO UPDATE
  SET category_id = EXCLUDED.category_id, name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, sale_price = EXCLUDED.sale_price, thumbnail_url = EXCLUDED.thumbnail_url;

  -- 양말 2개
  INSERT INTO public.products (category_id, name, slug, description, price, sale_price, status, thumbnail_url)
  VALUES
    (v_cat_acc_id, '데일리 코튼 골지 삭스 (5컬러 세트)', 'new-cotton-ribbed-socks-5pack', '부드러운 순면 100%와 짱짱한 골지 조직으로 흘러내림 없는 데일리 기본 양말 5켤레 세트입니다.', 15900, 12900, 'active', '/static/images/products/socks-1.jpg'),
    (v_cat_acc_id, '레트로 스포츠 스트라이프 크루 삭스 (3켤레 세트)', 'new-retro-stripe-crew-socks-3pack', '스포티한 2단 스트라이프 배색으로 스니커즈에 포인트 주기 좋은 크루 삭스 3켤레 세트입니다.', 11900, NULL, 'active', '/static/images/products/socks-2.jpg')
  ON CONFLICT (slug) DO UPDATE
  SET category_id = EXCLUDED.category_id, name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price, sale_price = EXCLUDED.sale_price, thumbnail_url = EXCLUDED.thumbnail_url;

END $$;

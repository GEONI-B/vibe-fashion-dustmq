-- ==============================================================================
-- VIBE-FASHION 쇼핑몰 데이터베이스 스키마 (Supabase PostgreSQL)
-- ==============================================================================

-- 0. 기존 테이블 및 객체 초기화 (필요시 순서대로 삭제)
-- DROP TABLE IF EXISTS reviews CASCADE;
-- DROP TABLE IF EXISTS notifications CASCADE;
-- DROP TABLE IF EXISTS refunds CASCADE;
-- DROP TABLE IF EXISTS order_items CASCADE;
-- DROP TABLE IF EXISTS orders CASCADE;
-- DROP TABLE IF EXISTS carts CASCADE;
-- DROP TABLE IF EXISTS product_images CASCADE;
-- DROP TABLE IF EXISTS product_options CASCADE;
-- DROP TABLE IF EXISTS products CASCADE;
-- DROP TABLE IF EXISTS categories CASCADE;
-- DROP TABLE IF EXISTS profiles CASCADE;

-- ------------------------------------------------------------------------------
-- 1. 공통 타임스탬프 갱신 트리거 함수
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ------------------------------------------------------------------------------
-- 2. profiles (회원 프로필 - auth.users와 1:1 연동)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT,
  name TEXT,
  avatar_url TEXT,
  phone TEXT,
  postal_code TEXT,
  address TEXT,
  address_detail TEXT,
  role TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
  grade TEXT NOT NULL DEFAULT 'BRONZE' CHECK (grade IN ('BRONZE', 'SILVER', 'GOLD', 'VIP')),
  total_spent NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (total_spent >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_profiles_updated_at
BEFORE UPDATE ON public.profiles
FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- 3. categories (카테고리)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.categories (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  parent_id BIGINT REFERENCES public.categories(id) ON DELETE SET NULL,
  display_order INT NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 4. products (상품)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id BIGINT REFERENCES public.categories(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  slug TEXT UNIQUE,
  description TEXT,
  price NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
  sale_price NUMERIC(12, 2) CHECK (sale_price >= 0 AND sale_price <= price),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'sold_out', 'hidden')),
  thumbnail_url TEXT,
  view_count INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_products_updated_at
BEFORE UPDATE ON public.products
FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- 5. product_options (상품 옵션 - 사이즈, 색상 등 및 재고 관리)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.product_options (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
  option_name TEXT NOT NULL,
  additional_price NUMERIC(12, 2) NOT NULL DEFAULT 0,
  stock_quantity INT NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
  sku TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 6. product_images (상품 추가 이미지)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.product_images (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
  image_url TEXT NOT NULL,
  display_order INT NOT NULL DEFAULT 0,
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 7. carts (장바구니)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.carts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
  option_id UUID REFERENCES public.product_options(id) ON DELETE CASCADE,
  quantity INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_cart_item UNIQUE (user_id, product_id, option_id)
);

CREATE TRIGGER trg_carts_updated_at
BEFORE UPDATE ON public.carts
FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- 8. orders (주문)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_number TEXT NOT NULL UNIQUE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'preparing', 'shipping', 'delivered', 'cancelled', 'refunded')),
  total_amount NUMERIC(12, 2) NOT NULL CHECK (total_amount >= 0),
  discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  shipping_fee NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (shipping_fee >= 0),
  payment_amount NUMERIC(12, 2) NOT NULL CHECK (payment_amount >= 0),
  payment_method TEXT,
  payment_id TEXT,
  recipient_name TEXT NOT NULL,
  recipient_phone TEXT NOT NULL,
  shipping_postal_code TEXT NOT NULL,
  shipping_address TEXT NOT NULL,
  shipping_address_detail TEXT,
  shipping_memo TEXT,
  tracking_number TEXT,
  paid_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_orders_updated_at
BEFORE UPDATE ON public.orders
FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- 9. order_items (주문 상세 품목 스냅샷)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.order_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  product_id UUID REFERENCES public.products(id) ON DELETE SET NULL,
  option_id UUID REFERENCES public.product_options(id) ON DELETE SET NULL,
  product_name TEXT NOT NULL,
  option_name TEXT,
  unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
  quantity INT NOT NULL CHECK (quantity > 0),
  total_price NUMERIC(12, 2) NOT NULL CHECK (total_price >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 10. refunds (환불/반품 신청 및 내역)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.refunds (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  order_item_id UUID REFERENCES public.order_items(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  reason TEXT NOT NULL,
  refund_amount NUMERIC(12, 2) NOT NULL CHECK (refund_amount >= 0),
  status TEXT NOT NULL DEFAULT 'requested' CHECK (status IN ('requested', 'approved', 'rejected', 'completed')),
  admin_memo TEXT,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at TIMESTAMPTZ
);

-- ------------------------------------------------------------------------------
-- 11. notifications (회원 알림)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  link_url TEXT,
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 12. reviews (상품 리뷰)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  order_item_id UUID REFERENCES public.order_items(id) ON DELETE SET NULL,
  rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  content TEXT NOT NULL,
  image_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_reviews_updated_at
BEFORE UPDATE ON public.reviews
FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- 13. 인덱스 생성 (조회 성능 최적화)
-- ------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_products_category_id ON public.products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_status ON public.products(status);
CREATE INDEX IF NOT EXISTS idx_product_options_product_id ON public.product_options(product_id);
CREATE INDEX IF NOT EXISTS idx_product_images_product_id ON public.product_images(product_id);
CREATE INDEX IF NOT EXISTS idx_carts_user_id ON public.carts(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON public.orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON public.orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON public.order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_refunds_order_id ON public.refunds(order_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON public.notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON public.reviews(product_id);

-- ==============================================================================
-- 14. auth.users 연동 트리거: handle_new_user
--     - 일반 가입 및 소셜 로그인(OAuth) 시 profiles 자동 생성
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
  v_name TEXT;
  v_avatar_url TEXT;
BEGIN
  -- 소셜 로그인 및 일반 메타데이터에서 이름 추출
  v_name := COALESCE(
    NEW.raw_user_meta_data->>'full_name',
    NEW.raw_user_meta_data->>'name',
    NEW.raw_user_meta_data->>'user_name',
    SPLIT_PART(NEW.email, '@', 1)
  );

  -- 아바타 URL 추출
  v_avatar_url := COALESCE(
    NEW.raw_user_meta_data->>'avatar_url',
    NEW.raw_user_meta_data->>'picture'
  );

  INSERT INTO public.profiles (
    id,
    email,
    name,
    avatar_url,
    role,
    grade,
    total_spent
  )
  VALUES (
    NEW.id,
    NEW.email,
    v_name,
    v_avatar_url,
    'customer',
    'BRONZE',
    0
  )
  ON CONFLICT (id) DO UPDATE
  SET
    email = EXCLUDED.email,
    name = COALESCE(public.profiles.name, EXCLUDED.name),
    avatar_url = COALESCE(public.profiles.avatar_url, EXCLUDED.avatar_url);

  RETURN NEW;
END;
$$;

-- auth.users 트리거 연결
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
AFTER INSERT ON auth.users
FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ==============================================================================
-- 15. 고객 등급 자동 업데이트 함수: update_customer_grade
--     - 누적 결제금액 기준:
--       VIP: 1,000,000원 이상
--       GOLD: 500,000원 이상
--       SILVER: 200,000원 이상
--       BRONZE: 200,000원 미만
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.update_customer_grade(p_user_id UUID)
RETURNS VOID
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
  v_total_paid NUMERIC(12, 2) := 0;
  v_total_refunded NUMERIC(12, 2) := 0;
  v_net_spent NUMERIC(12, 2) := 0;
  v_new_grade TEXT := 'BRONZE';
BEGIN
  -- 1) 결제 완료/배송 관련 주문 총 결제액 합산
  SELECT COALESCE(SUM(payment_amount), 0)
  INTO v_total_paid
  FROM public.orders
  WHERE user_id = p_user_id
    AND status IN ('paid', 'preparing', 'shipping', 'delivered');

  -- 2) 완료된 환불 금액 합산
  SELECT COALESCE(SUM(refund_amount), 0)
  INTO v_total_refunded
  FROM public.refunds
  WHERE user_id = p_user_id
    AND status = 'completed';

  -- 3) 실 누적 결제 금액 계산
  v_net_spent := GREATEST(v_total_paid - v_total_refunded, 0);

  -- 4) 등급 판정
  IF v_net_spent >= 1000000 THEN
    v_new_grade := 'VIP';
  ELSIF v_net_spent >= 500000 THEN
    v_new_grade := 'GOLD';
  ELSIF v_net_spent >= 200000 THEN
    v_new_grade := 'SILVER';
  ELSE
    v_new_grade := 'BRONZE';
  END IF;

  -- 5) 프로필 업데이트
  UPDATE public.profiles
  SET
    total_spent = v_net_spent,
    grade = v_new_grade,
    updated_at = NOW()
  WHERE id = p_user_id;
END;
$$;

-- 주문 상태 변경 또는 환불 완료 시 자동 등급 갱신용 트리거 함수
CREATE OR REPLACE FUNCTION public.handle_order_grade_update()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_TABLE_NAME = 'orders' THEN
    PERFORM public.update_customer_grade(NEW.user_id);
    IF (TG_OP = 'UPDATE' AND OLD.user_id <> NEW.user_id) THEN
      PERFORM public.update_customer_grade(OLD.user_id);
    END IF;
  ELSIF TG_TABLE_NAME = 'refunds' THEN
    PERFORM public.update_customer_grade(NEW.user_id);
  END IF;
  RETURN NEW;
END;
$$;

-- 주문 테이블 트리거
DROP TRIGGER IF EXISTS trg_orders_update_grade ON public.orders;
CREATE TRIGGER trg_orders_update_grade
AFTER INSERT OR UPDATE OF status, payment_amount ON public.orders
FOR EACH ROW EXECUTE FUNCTION public.handle_order_grade_update();

-- 환불 테이블 트리거
DROP TRIGGER IF EXISTS trg_refunds_update_grade ON public.refunds;
CREATE TRIGGER trg_refunds_update_grade
AFTER INSERT OR UPDATE OF status, refund_amount ON public.refunds
FOR EACH ROW EXECUTE FUNCTION public.handle_order_grade_update();

-- ==============================================================================
-- 16. Supabase Row Level Security (RLS) 활성화 및 기본 정책
-- ==============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_options ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.carts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.refunds ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;

-- 1) profiles: 본인 조회 및 수정
CREATE POLICY "profiles_select_own" ON public.profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "profiles_update_own" ON public.profiles FOR UPDATE USING (auth.uid() = id);

-- 2) 상품/카테고리/옵션/이미지: 모든 사용자 읽기 허용
CREATE POLICY "categories_read_all" ON public.categories FOR SELECT USING (is_active = TRUE);
CREATE POLICY "products_read_active" ON public.products FOR SELECT USING (status != 'hidden');
CREATE POLICY "product_options_read_all" ON public.product_options FOR SELECT USING (TRUE);
CREATE POLICY "product_images_read_all" ON public.product_images FOR SELECT USING (TRUE);

-- 3) carts: 본인 장바구니만 CRUD
CREATE POLICY "carts_all_own" ON public.carts FOR ALL USING (auth.uid() = user_id);

-- 4) orders / order_items: 본인 주문 조회 및 생성
CREATE POLICY "orders_select_own" ON public.orders FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "orders_insert_own" ON public.orders FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "order_items_select_own" ON public.order_items FOR SELECT
USING (EXISTS (SELECT 1 FROM public.orders o WHERE o.id = order_items.order_id AND o.user_id = auth.uid()));

-- 5) refunds: 본인 환불 신청 및 조회
CREATE POLICY "refunds_select_own" ON public.refunds FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "refunds_insert_own" ON public.refunds FOR INSERT WITH CHECK (auth.uid() = user_id);

-- 6) notifications: 본인 알림 조회 및 읽음 처리
CREATE POLICY "notifications_all_own" ON public.notifications FOR ALL USING (auth.uid() = user_id);

-- 7) reviews: 누구나 조회, 작성/수정은 본인만
CREATE POLICY "reviews_read_all" ON public.reviews FOR SELECT USING (TRUE);
CREATE POLICY "reviews_insert_own" ON public.reviews FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "reviews_update_own" ON public.reviews FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "reviews_delete_own" ON public.reviews FOR DELETE USING (auth.uid() = user_id);

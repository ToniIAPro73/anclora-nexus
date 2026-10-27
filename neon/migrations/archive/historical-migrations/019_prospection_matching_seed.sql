-- ============================================================================
-- Migration 019: Prospection & Buyer Matching v1 - Development Seed Data
-- Feature: ANCLORA-PBM-001
-- Safe for cloud/local:
--   - Uses real org_id from organizations
--   - Skips seed if no organization exists
--   - Idempotent by marker URL check
-- ============================================================================

DO $$
DECLARE
    v_org_id UUID;
    v_prop1  UUID;
    v_prop2  UUID;
    v_prop3  UUID;
    v_prop4  UUID;
    v_prop5  UUID;
    v_buyer1 UUID;
    v_buyer2 UUID;
    v_buyer3 UUID;
    v_match1 UUID;
    v_match2 UUID;
    v_match3 UUID;
    v_match4 UUID;
    v_already_seeded BOOLEAN := FALSE;
BEGIN
    -- 1) Resolve organization dynamically
    SELECT id
      INTO v_org_id
    FROM organizations
    ORDER BY created_at ASC
    LIMIT 1;

    IF v_org_id IS NULL THEN
        RAISE NOTICE 'Seed 019 skipped: no organizations found.';
        RETURN;
    END IF;

    -- 2) Idempotency guard (marker row by source_url)
    SELECT EXISTS (
        SELECT 1
        FROM prospected_properties
        WHERE org_id = v_org_id
          AND source_url = 'https://www.idealista.com/inmueble/12345'
    )
    INTO v_already_seeded;

    IF v_already_seeded THEN
        RAISE NOTICE 'Seed 019 skipped: demo records already exist for org %', v_org_id;
        RETURN;
    END IF;

    -- 3) Prospected Properties (5 samples)
    INSERT INTO prospected_properties (
        id, org_id, source, source_url, title, zone, city, price, property_type,
        bedrooms, bathrooms, area_m2, high_ticket_score, score_breakdown, status
    )
    VALUES
        (
            gen_random_uuid(), v_org_id, 'idealista', 'https://www.idealista.com/inmueble/12345',
            'Villa Mediterranea con vistas al mar', 'Port d''Andratx', 'Andratx',
            3250000.00, 'villa', 5, 4, 420.00, 92.50,
            '{"price": 38, "location": 24, "liquidity": 18, "quality": 12.5}'::jsonb,
            'new'
        )
    RETURNING id INTO v_prop1;

    INSERT INTO prospected_properties (
        id, org_id, source, source_url, title, zone, city, price, property_type,
        bedrooms, bathrooms, area_m2, high_ticket_score, score_breakdown, status
    )
    VALUES
        (
            gen_random_uuid(), v_org_id, 'fotocasa', 'https://www.fotocasa.es/prop/67890',
            'Apartamento premium frente al puerto', 'Port d''Andratx', 'Andratx',
            1850000.00, 'apartment', 3, 2, 185.00, 78.00,
            '{"price": 30, "location": 22, "liquidity": 16, "quality": 10}'::jsonb,
            'new'
        )
    RETURNING id INTO v_prop2;

    INSERT INTO prospected_properties (
        id, org_id, source, source_url, title, zone, city, price, property_type,
        bedrooms, bathrooms, area_m2, high_ticket_score, score_breakdown, status
    )
    VALUES
        (
            gen_random_uuid(), v_org_id, 'rightmove', 'https://www.rightmove.co.uk/overseas/12345',
            'Finca rustica reformada con piscina', 'Es Capdella', 'Calvia',
            2750000.00, 'finca', 6, 5, 800.00, 85.30,
            '{"price": 35, "location": 20, "liquidity": 17, "quality": 13.3}'::jsonb,
            'contacted'
        )
    RETURNING id INTO v_prop3;

    INSERT INTO prospected_properties (
        id, org_id, source, source_url, title, zone, city, price, property_type,
        bedrooms, bathrooms, area_m2, high_ticket_score, score_breakdown, status
    )
    VALUES
        (
            gen_random_uuid(), v_org_id, 'kyero', 'https://www.kyero.com/prop/98765',
            'Villa moderna minimalista', 'Son Ferrer', 'Calvia',
            1450000.00, 'villa', 4, 3, 310.00, 71.20,
            '{"price": 28, "location": 18, "liquidity": 14, "quality": 11.2}'::jsonb,
            'new'
        )
    RETURNING id INTO v_prop4;

    INSERT INTO prospected_properties (
        id, org_id, source, source_url, title, zone, city, price, property_type,
        bedrooms, bathrooms, area_m2, high_ticket_score, score_breakdown, status
    )
    VALUES
        (
            gen_random_uuid(), v_org_id, 'direct', NULL,
            'Atico duplex con terraza panoramica', 'Santa Ponsa', 'Calvia',
            980000.00, 'apartment', 3, 2, 150.00, 63.80,
            '{"price": 25, "location": 16, "liquidity": 12, "quality": 10.8}'::jsonb,
            'new'
        )
    RETURNING id INTO v_prop5;

    -- 4) Buyer Profiles (3 samples)
    INSERT INTO buyer_profiles (
        id, org_id, full_name, email, phone, budget_min, budget_max,
        preferred_zones, preferred_types, required_features,
        purchase_horizon, motivation_score, status
    )
    VALUES
        (
            gen_random_uuid(), v_org_id, 'Hans Mueller', 'hans.mueller@example.de', '+49 170 1234567',
            2000000.00, 4000000.00,
            ARRAY['Port d''Andratx', 'Es Capdella'],
            ARRAY['villa', 'finca'],
            '{"pool": true, "sea_view": true, "garage": true}'::jsonb,
            '3-6 months', 88.00, 'active'
        )
    RETURNING id INTO v_buyer1;

    INSERT INTO buyer_profiles (
        id, org_id, full_name, email, phone, budget_min, budget_max,
        preferred_zones, preferred_types, required_features,
        purchase_horizon, motivation_score, status
    )
    VALUES
        (
            gen_random_uuid(), v_org_id, 'Sarah Johnson', 'sarah.j@example.co.uk', '+44 7700 900123',
            1200000.00, 2200000.00,
            ARRAY['Port d''Andratx', 'Santa Ponsa', 'Son Ferrer'],
            ARRAY['apartment', 'villa'],
            '{"terrace": true, "parking": true}'::jsonb,
            '6-12 months', 72.00, 'active'
        )
    RETURNING id INTO v_buyer2;

    INSERT INTO buyer_profiles (
        id, org_id, full_name, email, phone, budget_min, budget_max,
        preferred_zones, preferred_types, required_features,
        purchase_horizon, motivation_score, status
    )
    VALUES
        (
            gen_random_uuid(), v_org_id, 'Pierre Dupont', 'pierre.d@example.fr', '+33 6 12 34 56 78',
            800000.00, 1500000.00,
            ARRAY['Son Ferrer', 'Santa Ponsa'],
            ARRAY['apartment'],
            '{"modern": true}'::jsonb,
            '12+ months', 55.00, 'active'
        )
    RETURNING id INTO v_buyer3;

    -- 5) Property-Buyer Matches (4 samples)
    INSERT INTO property_buyer_matches (
        id, org_id, property_id, buyer_id, match_score, score_breakdown, match_status, commission_estimate
    )
    VALUES
        (
            gen_random_uuid(), v_org_id, v_prop1, v_buyer1, 94.50,
            '{"budget": 33, "zone": 24, "type": 19, "horizon": 9, "motivation": 9.5}'::jsonb,
            'contacted', 97500.00
        )
    RETURNING id INTO v_match1;

    INSERT INTO property_buyer_matches (
        id, org_id, property_id, buyer_id, match_score, score_breakdown, match_status, commission_estimate
    )
    VALUES
        (
            gen_random_uuid(), v_org_id, v_prop3, v_buyer1, 87.20,
            '{"budget": 32, "zone": 23, "type": 16, "horizon": 8, "motivation": 8.2}'::jsonb,
            'candidate', 82500.00
        )
    RETURNING id INTO v_match2;

    INSERT INTO property_buyer_matches (
        id, org_id, property_id, buyer_id, match_score, score_breakdown, match_status, commission_estimate
    )
    VALUES
        (
            gen_random_uuid(), v_org_id, v_prop2, v_buyer2, 76.80,
            '{"budget": 28, "zone": 20, "type": 14, "horizon": 7, "motivation": 7.8}'::jsonb,
            'candidate', 55500.00
        )
    RETURNING id INTO v_match3;

    INSERT INTO property_buyer_matches (
        id, org_id, property_id, buyer_id, match_score, score_breakdown, match_status, commission_estimate
    )
    VALUES
        (
            gen_random_uuid(), v_org_id, v_prop5, v_buyer3, 68.40,
            '{"budget": 26, "zone": 18, "type": 12, "horizon": 6, "motivation": 6.4}'::jsonb,
            'candidate', 29400.00
        )
    RETURNING id INTO v_match4;

    -- 6) Match Activity Log (2 samples)
    INSERT INTO match_activity_log (org_id, match_id, activity_type, outcome, details)
    VALUES
        (
            v_org_id, v_match1, 'call', 'interested',
            '{"duration_min": 15, "notes": "Hans very interested. Requested viewing."}'::jsonb
        ),
        (
            v_org_id, v_match1, 'viewing', 'scheduled',
            '{"date": "2026-02-20", "time": "10:00", "notes": "Confirmed with owner."}'::jsonb
        );

    RAISE NOTICE 'Seed 019 inserted for org %: 5 properties, 3 buyers, 4 matches, 2 activities', v_org_id;
END;
$$;

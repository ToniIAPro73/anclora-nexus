-- VERIFICATION SCRIPT: verify_023.sql
-- Running this after migration 023

-- 1. Verificar distribución por source_system
SELECT source_system, count(*) 
FROM public.leads 
GROUP BY 1;

-- 2. Verificar distribución por source_channel
SELECT source_channel, count(*) 
FROM public.leads 
GROUP BY 1;

-- 3. Verificar que leads automáticos tengan captured_at
SELECT count(*) 
FROM public.leads 
WHERE captured_at IS NULL AND source_system <> 'manual';

-- 4. Verificar existencia de índices
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'leads' AND indexname LIKE 'idx_leads_org_%';

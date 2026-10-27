-- Migration 040: Seller contact channels for supervised outreach
-- Enables Gravity Claw HITL delivery via real email and WhatsApp clients.

ALTER TABLE IF EXISTS nexus_sellers
    ADD COLUMN IF NOT EXISTS email_contacto TEXT,
    ADD COLUMN IF NOT EXISTS telefono_contacto TEXT,
    ADD COLUMN IF NOT EXISTS whatsapp_contacto TEXT;

COMMENT ON COLUMN nexus_sellers.email_contacto IS
    'Primary seller email used for supervised mailto outreach.';

COMMENT ON COLUMN nexus_sellers.telefono_contacto IS
    'Primary seller phone number for calls and SMS context.';

COMMENT ON COLUMN nexus_sellers.whatsapp_contacto IS
    'WhatsApp-capable phone number used for supervised wa.me outreach.';

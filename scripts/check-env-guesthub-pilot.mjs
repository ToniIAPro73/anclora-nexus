// scripts/check-env-guesthub-pilot.mjs
// Env gate for the GuestHub controlled pilot (product renamed from Anclora
// SyncXML, 2026-08). Asserts the canonical GUESTHUB_* names in .env.example;
// the backend still accepts the legacy SYNCXML_* names as runtime fallback.
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const envPath = path.join(__dirname, '..', '.env.example');

const REQUIRED_VARS = [
  'NEON_DATA_API_URL',
  'NEON_JWT_PRIVATE_KEY',
  'PUBLIC_CTA_ORG_ID',
  'GUESTHUB_WEBHOOK_SECRET',
  'GUESTHUB_INTERNAL_API_URL',
  'GUESTHUB_INTERNAL_API_SECRET',
  'GUESTHUB_APP_URL',
  'GUESTHUB_LOGIN_URL',
  'HERMES_WORKER_URL',
  'HERMES_WORKER_API_KEY',
  'RESEND_API_KEY',
  'RESEND_FROM_EMAIL'
];

function checkEnv() {
  if (!fs.existsSync(envPath)) {
    console.error('❌ .env.example not found');
    process.exit(1);
  }

  const content = fs.readFileSync(envPath, 'utf8');
  let missing = [];

  for (const v of REQUIRED_VARS) {
    const regex = new RegExp(`^${v}=`, 'm');
    if (!regex.test(content)) {
      missing.push(v);
    }
  }

  if (missing.length > 0) {
    console.error('❌ Missing required variables in .env.example:');
    missing.forEach(m => console.error(`  - ${m}`));
    process.exit(1);
  }

  console.log('✅ .env.example has all required variables for GuestHub Pilot.');
}

checkEnv();

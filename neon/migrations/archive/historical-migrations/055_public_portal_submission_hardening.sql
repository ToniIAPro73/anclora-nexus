alter table public.partner_admissions
    add column if not exists submission_language text not null default 'es',
    add column if not exists privacy_accepted boolean not null default false,
    add column if not exists newsletter_opt_in boolean not null default false,
    add column if not exists captcha_provider text,
    add column if not exists captcha_verified_at timestamptz,
    add column if not exists confirmation_email_sent_at timestamptz;

alter table public.data_lab_access_requests
    add column if not exists submission_language text not null default 'es',
    add column if not exists privacy_accepted boolean not null default false,
    add column if not exists newsletter_opt_in boolean not null default false,
    add column if not exists captcha_provider text,
    add column if not exists captcha_verified_at timestamptz,
    add column if not exists confirmation_email_sent_at timestamptz;

comment on column public.partner_admissions.submission_language is
    'Language selected by the applicant when the partner admission was submitted.';
comment on column public.partner_admissions.privacy_accepted is
    'Whether the applicant accepted the privacy policy at submission time.';
comment on column public.partner_admissions.newsletter_opt_in is
    'Whether the applicant opted into Anclora briefings when the partner admission was submitted.';
comment on column public.partner_admissions.captcha_provider is
    'Captcha provider used during submission, if any.';
comment on column public.partner_admissions.captcha_verified_at is
    'Timestamp of server-side captcha verification.';
comment on column public.partner_admissions.confirmation_email_sent_at is
    'Timestamp of the submission confirmation email, if sent.';

comment on column public.data_lab_access_requests.submission_language is
    'Language selected by the applicant when the Data Lab access request was submitted.';
comment on column public.data_lab_access_requests.privacy_accepted is
    'Whether the applicant accepted the privacy policy at submission time.';
comment on column public.data_lab_access_requests.newsletter_opt_in is
    'Whether the applicant opted into Anclora briefings when the Data Lab request was submitted.';
comment on column public.data_lab_access_requests.captcha_provider is
    'Captcha provider used during submission, if any.';
comment on column public.data_lab_access_requests.captcha_verified_at is
    'Timestamp of server-side captcha verification.';
comment on column public.data_lab_access_requests.confirmation_email_sent_at is
    'Timestamp of the submission confirmation email, if sent.';

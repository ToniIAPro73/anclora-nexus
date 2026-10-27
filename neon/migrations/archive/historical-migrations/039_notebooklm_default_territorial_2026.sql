-- Migration 039: Align NotebookLM default notebook name with active territorial notebook
-- Keeps historical migration 036 intact while updating the runtime default for new rows.

ALTER TABLE notebooklm_insights
    ALTER COLUMN notebook_name
    SET DEFAULT 'Inteligencia Territorial Suroeste Mallorca 2026';

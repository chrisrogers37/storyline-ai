-- Migration 010: Add show_verbose_notifications to chat_settings
-- This column controls whether verbose text (workflow instructions) is shown in notifications

ALTER TABLE chat_settings
ADD COLUMN show_verbose_notifications BOOLEAN DEFAULT true;

COMMENT ON COLUMN chat_settings.show_verbose_notifications IS
    'When true, show detailed workflow instructions in posting notifications. When false, show minimal info.';

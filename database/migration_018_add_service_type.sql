-- migration_018_add_service_type.sql
-- Adds service_type and laser_options columns to print_requests.
-- service_type: '3dprint' (default) | 'laser'
-- laser_options: JSON string, nullable (only used when service_type='laser')
-- Rollback:
--   ALTER TABLE print_requests DROP COLUMN service_type;
--   ALTER TABLE print_requests DROP COLUMN laser_options;

ALTER TABLE print_requests
  ADD COLUMN service_type VARCHAR(20) NOT NULL DEFAULT '3dprint',
  ADD COLUMN laser_options TEXT NULL;

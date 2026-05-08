-- Migration 016: Fix accepted_file_formats for laser printers that still have 3D-print formats
-- Run once to correct DB data for any laser printers whose formats were set before laser support was added.

UPDATE printers
SET accepted_file_formats = 'svg,dxf,pdf'
WHERE device_type = 'laser'
  AND (
    accepted_file_formats IS NULL
    OR accepted_file_formats = ''
    OR accepted_file_formats REGEXP '^(ufp|3mf|stl)(,(ufp|3mf|stl))*$'
  );

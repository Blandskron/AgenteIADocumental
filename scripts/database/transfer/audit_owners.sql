-- Read-only aggregate. Numeric shape cannot prove historical Auth ownership:
-- a former numeric username/sub is indistinguishable from user_id here.
-- Never auto-reassign, merge, or delete ambiguous history from these counts.
BEGIN READ ONLY;
SELECT CASE
    WHEN owner_user_id = 'unknown' THEN 'unresolved_unknown'
    WHEN owner_user_id ~ '^[1-9][0-9]*$' THEN 'canonical_numeric_unverified'
    WHEN owner_user_id ~ '^[0-9]+$' THEN 'noncanonical_numeric'
    ELSE 'noncanonical_other'
END AS owner_category, count(*) AS event_count
FROM public.transfer_events
GROUP BY owner_category
ORDER BY owner_category;
COMMIT;

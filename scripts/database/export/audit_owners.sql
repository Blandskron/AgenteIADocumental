-- Read-only inventory: report counts, never infer ownership or reveal document details.
SELECT count(*) AS total_exports,
       count(*) FILTER (
           WHERE e.owner_user_id !~ '^[1-9][0-9]{0,18}$'
              OR (length(e.owner_user_id)=19 AND e.owner_user_id>'9223372036854775807')
       ) AS noncanonical_owners,
       count(*) FILTER (WHERE u.id IS NULL) AS owners_without_current_account
FROM public.document_exports AS e
LEFT JOIN public.auth_user AS u ON u.id::text=e.owner_user_id;

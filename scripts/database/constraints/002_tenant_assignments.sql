-- Included inside one transaction, with writers stopped or blocked by these locks.
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog, public;
LOCK TABLE public.tenant_groups, public.tenant_memberships, public.tenant_user_groups
    IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE bad_group bigint; bad_membership bigint; spec record; actual text; valid boolean;
BEGIN
    SELECT count(*) INTO bad_group FROM public.tenant_user_groups a
      LEFT JOIN public.tenant_groups g ON g.group_id=a.group_id AND g.tenant_id=a.tenant_id
      WHERE g.group_id IS NULL;
    SELECT count(*) INTO bad_membership FROM public.tenant_user_groups a
      WHERE NOT EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=a.tenant_id AND m.user_id=a.user_id);
    IF bad_group > 0 OR bad_membership > 0 THEN
        RAISE EXCEPTION 'Tenant assignment preflight failed (group: %, membership: %). Review historical data.', bad_group, bad_membership;
    END IF;
    FOR spec IN SELECT * FROM (VALUES
      ('tenant_groups','tenant_groups_tenant_id_group_id_key', 'UNIQUE (tenant_id, group_id)'),
      ('tenant_user_groups','tenant_assignments_group_tenant_fk', 'FOREIGN KEY (tenant_id, group_id) REFERENCES tenant_groups(tenant_id, group_id) ON DELETE CASCADE'),
      ('tenant_user_groups','tenant_assignments_membership_fk', 'FOREIGN KEY (tenant_id, user_id) REFERENCES tenant_memberships(tenant_id, user_id) ON DELETE CASCADE')
    ) AS x(table_name, constraint_name, definition) LOOP
        SELECT pg_get_constraintdef(c.oid), c.convalidated INTO actual, valid
          FROM pg_constraint c WHERE c.conrelid=format('public.%I',spec.table_name)::regclass AND c.conname=spec.constraint_name;
        IF FOUND THEN
            IF actual IS DISTINCT FROM spec.definition OR valid IS DISTINCT FROM true THEN
                RAISE EXCEPTION 'Unexpected tenant assignment constraint definition. Review schema drift.';
            END IF;
        ELSE
            EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I %s', spec.table_name, spec.constraint_name, spec.definition);
        END IF;
    END LOOP;
END $$;

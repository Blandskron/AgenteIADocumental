-- Transactional activation; public user fields and document bytes are preserved.
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog, public, pg_temp;
LOCK TABLE public.tenants, public.tenant_areas, public.tenant_memberships, public.documents
    IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE bad_parent bigint; bad_member bigint; bad_document bigint;
        spec record; actual text; valid boolean; column_info record;
BEGIN
    FOR spec IN SELECT * FROM (VALUES
      ('tenant_areas','tenant_id',true), ('tenant_areas','area_id',true), ('tenant_areas','parent_area_id',false),
      ('tenant_memberships','tenant_id',true), ('tenant_memberships','area_id',false),
      ('documents','tenant_id',false), ('documents','owner_area_id',false)
    ) AS x(table_name,column_name,required) LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_attribute a
          WHERE a.attrelid=format('public.%I',spec.table_name)::regclass AND a.attname=spec.column_name
            AND NOT a.attisdropped AND a.atttypid='text'::regtype
            AND a.attnotnull=spec.required AND a.attgenerated='') THEN
            RAISE EXCEPTION 'Unexpected tenant relation column. Review schema drift.';
        END IF;
    END LOOP;
    -- An additional CASCADE FK could defeat the verified SET NULL action.
    IF EXISTS (SELECT 1 FROM pg_constraint c
      WHERE c.contype='f' AND c.conrelid IN ('public.tenant_areas'::regclass,'public.tenant_memberships'::regclass,'public.documents'::regclass)
        AND c.conkey && ARRAY(SELECT a.attnum FROM pg_attribute a WHERE a.attrelid=c.conrelid
          AND a.attname IN ('tenant_id','parent_area_id','area_id','owner_area_id','owner_area_tenant_id'))
        AND NOT ((c.conrelid='public.tenant_areas'::regclass AND c.conname IN ('tenant_areas_tenant_id_fkey','tenant_areas_parent_area_id_fkey','tenant_areas_parent_tenant_fk'))
          OR (c.conrelid='public.tenant_memberships'::regclass AND c.conname IN ('tenant_memberships_tenant_id_fkey','tenant_memberships_area_id_fkey','tenant_memberships_area_tenant_fk'))
          OR (c.conrelid='public.documents'::regclass AND c.conname IN ('documents_tenant_id_fkey','documents_owner_area_id_fkey','documents_area_tenant_fk')))) THEN
        RAISE EXCEPTION 'Unexpected tenant lifecycle foreign key. Review schema drift.';
    END IF;
    SELECT count(*) INTO bad_parent FROM public.tenant_areas a
      LEFT JOIN public.tenant_areas p ON p.area_id=a.parent_area_id AND p.tenant_id=a.tenant_id
      WHERE a.parent_area_id IS NOT NULL AND p.area_id IS NULL;
    SELECT count(*) INTO bad_member FROM public.tenant_memberships m
      LEFT JOIN public.tenant_areas a ON a.area_id=m.area_id AND a.tenant_id=m.tenant_id
      WHERE m.area_id IS NOT NULL AND a.area_id IS NULL;
    SELECT count(*) INTO bad_document FROM public.documents d
      LEFT JOIN public.tenant_areas a ON a.area_id=d.owner_area_id AND a.tenant_id=d.tenant_id
      WHERE d.owner_area_id IS NOT NULL AND a.area_id IS NULL;
    IF bad_parent > 0 OR bad_member > 0 OR bad_document > 0 THEN
        RAISE EXCEPTION 'Tenant area preflight failed (parent: %, membership: %, document: %). Review historical data.',
          bad_parent, bad_member, bad_document;
    END IF;

    -- MATCH FULL needs both components null for an optional area. The generated
    -- component avoids forbidding tenant documents without an area and cannot
    -- be supplied by clients. Existing SET NULL clears owner_area_id on deletion.
    SELECT a.attgenerated, a.atttypid, a.attnotnull, pg_get_expr(d.adbin,d.adrelid) AS expression
      INTO column_info FROM pg_attribute a LEFT JOIN pg_attrdef d
        ON d.adrelid=a.attrelid AND d.adnum=a.attnum
      WHERE a.attrelid='public.documents'::regclass AND a.attname='owner_area_tenant_id' AND NOT a.attisdropped;
    IF FOUND THEN
        IF column_info.attgenerated <> 's' OR column_info.atttypid <> 'text'::regtype OR column_info.attnotnull
           OR regexp_replace(column_info.expression, '\s+', '', 'g') IS DISTINCT FROM
             'CASEWHEN(owner_area_idISNOTNULL)THENtenant_idELSENULL::textEND' THEN
            RAISE EXCEPTION 'Unexpected document area generated column. Review schema drift.';
        END IF;
    ELSE
        ALTER TABLE public.documents ADD COLUMN owner_area_tenant_id text
          GENERATED ALWAYS AS (CASE WHEN owner_area_id IS NOT NULL THEN tenant_id ELSE NULL END) STORED;
    END IF;

    FOR spec IN SELECT * FROM (VALUES
      ('tenant_areas','tenant_areas_tenant_id_fkey','FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE'),
      ('tenant_areas','tenant_areas_parent_area_id_fkey','FOREIGN KEY (parent_area_id) REFERENCES tenant_areas(area_id) ON DELETE SET NULL'),
      ('tenant_memberships','tenant_memberships_tenant_id_fkey','FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE'),
      ('tenant_memberships','tenant_memberships_area_id_fkey','FOREIGN KEY (area_id) REFERENCES tenant_areas(area_id) ON DELETE SET NULL'),
      ('documents','documents_tenant_id_fkey','FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE SET NULL'),
      ('tenant_areas','tenant_areas_tenant_area_key','UNIQUE (tenant_id, area_id)'),
      ('tenant_areas','tenant_areas_parent_tenant_fk','FOREIGN KEY (tenant_id, parent_area_id) REFERENCES tenant_areas(tenant_id, area_id) ON DELETE SET NULL (parent_area_id)'),
      ('tenant_memberships','tenant_memberships_area_tenant_fk','FOREIGN KEY (tenant_id, area_id) REFERENCES tenant_areas(tenant_id, area_id) ON DELETE SET NULL (area_id)'),
      ('documents','documents_owner_area_id_fkey','FOREIGN KEY (owner_area_id) REFERENCES tenant_areas(area_id) ON DELETE SET NULL'),
      ('documents','documents_area_tenant_fk','FOREIGN KEY (owner_area_tenant_id, owner_area_id) REFERENCES tenant_areas(tenant_id, area_id) MATCH FULL DEFERRABLE INITIALLY DEFERRED')
    ) AS x(table_name,constraint_name,definition) LOOP
        SELECT pg_get_constraintdef(c.oid), c.convalidated INTO actual, valid FROM pg_constraint c
          WHERE c.conrelid=format('public.%I',spec.table_name)::regclass AND c.conname=spec.constraint_name;
        IF FOUND THEN
            IF actual IS DISTINCT FROM spec.definition OR valid IS DISTINCT FROM true THEN
                RAISE EXCEPTION 'Unexpected tenant area constraint definition. Review schema drift.';
            END IF;
        ELSE
            EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I %s',spec.table_name,spec.constraint_name,spec.definition);
        END IF;
    END LOOP;
END $$;

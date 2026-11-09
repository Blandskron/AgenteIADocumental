-- Included in a schema-operator transaction AFTER Django's Auth migrations.
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog, public, pg_temp;
LOCK TABLE public.auth_user, public.tenant_memberships IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE bad bigint; info record; expected text; actual text; spec record; valid boolean;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_attribute WHERE attrelid='public.auth_user'::regclass
          AND attname='id' AND atttypid='integer'::regtype AND attnotnull
          AND attgenerated='' AND NOT attisdropped
    ) THEN
        RAISE EXCEPTION 'Unexpected Auth identity column. Review schema drift.';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_attribute WHERE attrelid='public.tenant_memberships'::regclass
          AND attname='user_id' AND atttypid='text'::regtype AND attnotnull
          AND attgenerated='' AND NOT attisdropped
    ) THEN
        RAISE EXCEPTION 'Unexpected membership user column. Review schema drift.';
    END IF;
    SELECT count(*) INTO bad FROM public.tenant_memberships m
      LEFT JOIN public.auth_user u ON u.id::text=m.user_id
      WHERE u.id IS NULL OR m.user_id COLLATE "C" !~ '^[1-9][0-9]{0,9}$';
    IF bad>0 THEN
        RAISE EXCEPTION 'Membership identity preflight requires review (rows: %).',bad;
    END IF;

    -- Use PostgreSQL's own expression deparser to compare against a blueprint.
    CREATE TEMP TABLE tenant_identity_blueprint (
        user_id text,
        auth_user_id bigint GENERATED ALWAYS AS (
            CASE WHEN user_id COLLATE "C" ~ '^[1-9][0-9]{0,9}$'
              THEN user_id::bigint ELSE NULL END
        ) STORED
    ) ON COMMIT DROP;
    SELECT pg_get_expr(adbin,adrelid) INTO expected FROM pg_attrdef
      WHERE adrelid='pg_temp.tenant_identity_blueprint'::regclass;
    SELECT a.*,pg_get_expr(d.adbin,d.adrelid) AS expression INTO info
      FROM pg_attribute a LEFT JOIN pg_attrdef d
        ON d.adrelid=a.attrelid AND d.adnum=a.attnum
      WHERE a.attrelid='public.tenant_memberships'::regclass
        AND a.attname='auth_user_id' AND NOT a.attisdropped;
    IF FOUND THEN
        IF info.attgenerated<>'s' OR info.atttypid<>'bigint'::regtype
          OR info.attnotnull OR info.expression IS DISTINCT FROM expected THEN
            RAISE EXCEPTION 'Unexpected membership identity column. Review schema drift.';
        END IF;
    ELSE
        ALTER TABLE public.tenant_memberships ADD COLUMN auth_user_id bigint
          GENERATED ALWAYS AS (
            CASE WHEN user_id COLLATE "C" ~ '^[1-9][0-9]{0,9}$'
              THEN user_id::bigint ELSE NULL END
          ) STORED;
    END IF;
    DROP TABLE pg_temp.tenant_identity_blueprint;

    IF EXISTS (
        SELECT 1 FROM pg_constraint c WHERE c.conrelid='public.tenant_memberships'::regclass
          AND c.contype='f' AND c.conname<>'tenant_memberships_auth_user_fk'
          AND c.conkey && ARRAY(SELECT attnum FROM pg_attribute
            WHERE attrelid=c.conrelid AND attname IN ('user_id','auth_user_id'))
    ) THEN
        RAISE EXCEPTION 'Unexpected membership identity foreign key. Review schema drift.';
    END IF;
    FOR spec IN SELECT * FROM (VALUES
      ('tenant_memberships_auth_user_check','CHECK ((auth_user_id IS NOT NULL))'),
      ('tenant_memberships_auth_user_fk','FOREIGN KEY (auth_user_id) REFERENCES auth_user(id) ON DELETE CASCADE')
    ) AS x(name,definition) LOOP
        SELECT pg_get_constraintdef(c.oid),c.convalidated INTO actual,valid
          FROM pg_constraint c WHERE c.conrelid='public.tenant_memberships'::regclass
            AND c.conname=spec.name;
        IF FOUND THEN
            IF actual IS DISTINCT FROM spec.definition OR valid IS DISTINCT FROM true THEN
                RAISE EXCEPTION 'Unexpected membership identity constraint. Review schema drift.';
            END IF;
        ELSE
            EXECUTE format('ALTER TABLE public.tenant_memberships ADD CONSTRAINT %I %s',spec.name,spec.definition);
        END IF;
    END LOOP;
    IF (SELECT count(*) FROM pg_trigger t JOIN pg_constraint c ON c.oid=t.tgconstraint
        WHERE c.conrelid='public.tenant_memberships'::regclass
          AND c.conname='tenant_memberships_auth_user_fk' AND t.tgisinternal
          AND t.tgenabled='O')<>4 THEN
        RAISE EXCEPTION 'Unexpected membership identity enforcement. Review schema drift.';
    END IF;
    SELECT i.*,pg_get_indexdef(i.indexrelid) AS definition INTO info
      FROM pg_index i WHERE i.indexrelid=to_regclass('public.tenant_memberships_auth_user_idx');
    IF FOUND THEN
        IF info.definition IS DISTINCT FROM
          'CREATE INDEX tenant_memberships_auth_user_idx ON public.tenant_memberships USING btree (auth_user_id)'
          OR NOT info.indisvalid OR NOT info.indisready THEN
            RAISE EXCEPTION 'Unexpected membership identity index. Review schema drift.';
        END IF;
    ELSE
        CREATE INDEX tenant_memberships_auth_user_idx ON public.tenant_memberships(auth_user_id);
    END IF;
END $$;

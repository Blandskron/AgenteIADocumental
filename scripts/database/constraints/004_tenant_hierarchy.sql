SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = pg_catalog, public, pg_temp;
LOCK TABLE public.tenants, public.tenant_areas IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE cycles bigint; unresolved bigint; info record; actual text;
        body text := $body$
BEGIN
    IF TG_OP='UPDATE' THEN
        IF NEW.area_id IS DISTINCT FROM OLD.area_id OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
            RAISE EXCEPTION 'Area identity is immutable.' USING ERRCODE='23514',CONSTRAINT='tenant_areas_identity_immutable';
        END IF;
        IF NEW.parent_area_id IS NOT DISTINCT FROM OLD.parent_area_id THEN RETURN NEW; END IF;
    END IF;
    -- Removing an edge cannot create a cycle and must also work during a tenant cascade.
    IF NEW.parent_area_id IS NULL THEN RETURN NEW; END IF;
    IF NEW.parent_area_id=NEW.area_id THEN
        RAISE EXCEPTION 'Area hierarchy would contain a cycle.' USING ERRCODE='23514',CONSTRAINT='tenant_areas_acyclic';
    END IF;
    -- A real row UPDATE serializes topology writers; at RR/Serializable a stale
    -- contender gets 40001 instead of validating against its earlier snapshot.
    UPDATE public.tenants SET area_revision=area_revision+1 WHERE tenant_id=NEW.tenant_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Area tenant is unavailable.' USING ERRCODE='23503',CONSTRAINT='tenant_areas_tenant_id_fkey';
    END IF;
    PERFORM 1 FROM public.tenant_areas WHERE area_id=NEW.parent_area_id AND tenant_id=NEW.tenant_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'An existing parent in the same tenant is required.' USING ERRCODE='23503',CONSTRAINT='tenant_areas_parent_tenant_fk';
    END IF;
    IF EXISTS (WITH RECURSIVE ancestors AS (
        SELECT area_id,parent_area_id FROM public.tenant_areas WHERE area_id=NEW.parent_area_id AND tenant_id=NEW.tenant_id
        UNION
        SELECT a.area_id,a.parent_area_id FROM public.tenant_areas a JOIN ancestors p ON a.area_id=p.parent_area_id WHERE a.tenant_id=NEW.tenant_id
    ) SELECT 1 FROM ancestors WHERE area_id=NEW.area_id) THEN
        RAISE EXCEPTION 'Area hierarchy would contain a cycle.' USING ERRCODE='23514',CONSTRAINT='tenant_areas_acyclic';
    END IF;
    RETURN NEW;
END
$body$;
BEGIN
    WITH RECURSIVE walk(start_id,next_id,path,cycle,depth) AS (
      SELECT area_id,parent_area_id,ARRAY[area_id],false,1 FROM public.tenant_areas WHERE parent_area_id IS NOT NULL
      UNION ALL
      SELECT w.start_id,a.parent_area_id,w.path||a.area_id,a.area_id=ANY(w.path),w.depth+1
      FROM walk w JOIN public.tenant_areas a ON a.area_id=w.next_id WHERE NOT w.cycle AND w.depth<256
    ) SELECT count(DISTINCT start_id) FILTER(WHERE cycle),
             count(DISTINCT start_id) FILTER(WHERE depth=256 AND next_id IS NOT NULL AND NOT cycle)
      INTO cycles,unresolved FROM walk;
    IF cycles>0 OR unresolved>0 THEN
        RAISE EXCEPTION 'Area hierarchy preflight requires review (cycles: %, unresolved: %).',cycles,unresolved;
    END IF;
    SELECT a.attnotnull,a.atttypid,a.attgenerated,pg_get_expr(d.adbin,d.adrelid) AS expression INTO info
      FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
      WHERE a.attrelid='public.tenants'::regclass AND a.attname='area_revision' AND NOT a.attisdropped;
    IF FOUND THEN
        IF NOT info.attnotnull OR info.atttypid<>'bigint'::regtype OR info.attgenerated<>'' OR info.expression IS DISTINCT FROM '0' THEN
            RAISE EXCEPTION 'Unexpected area revision column. Review schema drift.';
        END IF;
    ELSE
        ALTER TABLE public.tenants ADD COLUMN area_revision bigint NOT NULL DEFAULT 0;
    END IF;
    SELECT p.* INTO info FROM pg_proc p WHERE p.oid=to_regprocedure('public.guard_tenant_area_hierarchy()');
    IF FOUND THEN
        IF info.prosrc IS DISTINCT FROM body OR info.prosecdef OR info.provolatile<>'v'
          OR info.prolang<>(SELECT oid FROM pg_language WHERE lanname='plpgsql')
          OR info.prokind<>'f' OR info.proisstrict OR info.proleakproof OR info.proparallel<>'u'
          OR info.prorettype<>'trigger'::regtype
          OR info.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog, pg_temp','lock_timeout=5s']
          OR EXISTS(SELECT 1 FROM aclexplode(COALESCE(info.proacl,acldefault('f',info.proowner))) acl WHERE acl.grantee<>info.proowner) THEN
            RAISE EXCEPTION 'Unexpected hierarchy function. Review schema drift.';
        END IF;
    ELSE
        EXECUTE format('CREATE FUNCTION public.guard_tenant_area_hierarchy() RETURNS trigger LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog,pg_temp SET lock_timeout=%L AS %L','5s',body);
        REVOKE ALL ON FUNCTION public.guard_tenant_area_hierarchy() FROM PUBLIC;
    END IF;
    SELECT t.*,pg_get_triggerdef(t.oid) AS definition INTO info FROM pg_trigger t
      WHERE t.tgrelid='public.tenant_areas'::regclass AND t.tgname='tenant_areas_hierarchy_guard';
    IF FOUND THEN
        actual := 'CREATE TRIGGER tenant_areas_hierarchy_guard BEFORE INSERT OR UPDATE OF area_id, tenant_id, parent_area_id ON public.tenant_areas FOR EACH ROW EXECUTE FUNCTION guard_tenant_area_hierarchy()';
        IF info.definition IS DISTINCT FROM actual OR info.tgenabled<>'O' OR info.tgisinternal THEN
            RAISE EXCEPTION 'Unexpected hierarchy trigger. Review schema drift.';
        END IF;
    ELSE
        CREATE TRIGGER tenant_areas_hierarchy_guard BEFORE INSERT OR UPDATE OF area_id,tenant_id,parent_area_id
          ON public.tenant_areas FOR EACH ROW EXECUTE FUNCTION public.guard_tenant_area_hierarchy();
    END IF;
END $$;

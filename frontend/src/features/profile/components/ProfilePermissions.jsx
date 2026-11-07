export function ProfilePermissions({ user }) {
  const membership = user?.tenantMemberships?.find((item) => String(item.tenant_id) === String(user.activeTenantId));
  const permissions = [...new Set((user?.permissions || []).filter((item) => typeof item === "string"))].sort();
  return (
    <section className="profile-card profile-permissions" aria-labelledby="profile-permissions-title">
      <div className="profile-card-header">
        <h3 id="profile-permissions-title">Permisos efectivos de la sesión</h3>
        <p>Auth determina estos permisos para el tenant activo. Los servicios comprueban cada operación.</p>
      </div>
      <dl>
        <dt>Tenant activo</dt><dd>{membership?.tenant_name || user?.activeTenantId || "Sin tenant activo"}</dd>
        <dt>Rol activo</dt><dd>{user?.activeTenantRole || "Sin rol asignado"}</dd>
        <dt>Grupos del tenant activo</dt><dd>{membership?.groups?.join(", ") || "Sin grupos asignados"}</dd>
      </dl>
      {user?.isSuperuser && <p>Superusuario del sistema. El alcance sigue sujeto a cada servicio.</p>}
      {permissions.length ? <ul aria-label="Permisos efectivos">{permissions.map((permission) =>
        <li key={permission}><code>{permission === "*" ? "* (todos los permisos de Auth)" : permission}</code></li>)}</ul>
        : <p>No hay permisos efectivos asignados en esta sesión.</p>}
      <p>Staff y los grupos globales no conceden por sí solos permisos del tenant. Los cambios se consultan de nuevo al renovar la sesión.</p>
    </section>
  );
}

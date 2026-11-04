import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Building2,
  Check,
  CircleAlert,
  FolderTree,
  Hash,
  KeyRound,
  Loader2,
  Menu,
  Save,
  ShieldCheck,
  UserPlus,
  UsersRound,
} from "lucide-react";

import { useAuthContext } from "../../app/providers/AuthProvider";
import { appRoutes } from "../../app/router/routes";
import { isTenantAdmin } from "../../entities/auth/model/auth.user";
import { listUsers } from "../../features/auth/api/user-management.api";
import {
  TENANT_PERMISSION_OPTIONS,
  assignTenantUserGroup,
  createTenant,
  createTenantArea,
  createTenantGroup,
  provisionTenantUser,
  listTenantAreas,
  listTenantGroups,
  listTenantMemberships,
  listTenants,
  listTenantUserGroups,
  updateTenantGroup,
} from "../../features/tenant-admin/api/tenant-admin.api";
import { AppShell } from "../../shared/layouts/AppShell";
import { IconButton } from "../../shared/components/IconButton/IconButton";
import { Sidebar } from "../../widgets/Sidebar/Sidebar";
import "./AdminPage.css";

const ROLE_OPTIONS = [
  { value: "TENANT_ADMIN", label: "Admin empresa" },
  { value: "LEADER", label: "Lider" },
  { value: "USER", label: "Usuario" },
];

const PERMISSION_LABELS = {
  view_documents: "Ver documentos",
  upload_documents: "Subir documentos",
  download_documents: "Descargar documentos",
  assign_documents: "Asignar documentos",
  approve_documents: "Aprobar documentos",
  reject_documents: "Rechazar documentos",
  sign_documents: "Firmar documentos",
  manage_documents: "Gestionar documentos",
  manage_users: "Gestionar usuarios",
  manage_areas: "Gestionar areas",
  manage_groups: "Gestionar grupos",
  use_chat: "Usar chat IA",
  use_google_drive: "Conectar Google Drive",
  use_sharepoint: "Conectar SharePoint",
  view_audit_logs: "Ver auditoria",
};

export function AdminPage({ onNavigate }) {
  const { authClient, currentUser, logout } = useAuthContext();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [tenants, setTenants] = useState([]);
  const [users, setUsers] = useState([]);
  const [areas, setAreas] = useState([]);
  const [memberships, setMemberships] = useState([]);
  const [tenantGroups, setTenantGroups] = useState([]);
  const [tenantUserGroups, setTenantUserGroups] = useState([]);
  const fallbackTenant = useMemo(
    () =>
      currentUser?.activeTenant
        ? {
            tenantId: currentUser.activeTenantId,
            name: currentUser.activeTenant.tenant_name || currentUser.activeTenant.name || "Mi empresa",
            status: "ACTIVE",
          }
        : null,
    [currentUser?.activeTenant, currentUser?.activeTenantId],
  );
  const [selectedTenantId, setSelectedTenantId] = useState(currentUser?.activeTenantId || "");
  const [tenantForm, setTenantForm] = useState({ name: "", taxId: "" });
  const [areaForm, setAreaForm] = useState({ name: "", parentAreaId: "" });
  const [userForm, setUserForm] = useState({
    username: "",
    email: "",
    firstName: "",
    lastName: "",
    password: "",
    role: "USER",
    areaId: "",
  });
  const [groupForm, setGroupForm] = useState({
    groupId: "",
    name: "Usuarios",
    description: "",
    permissions: ["view_documents", "download_documents"],
  });
  const [assignGroupForm, setAssignGroupForm] = useState({ userId: "", groupId: "" });

  const availableTenants = tenants.length ? tenants : fallbackTenant ? [fallbackTenant] : [];
  const selectedTenant = availableTenants.find((tenant) => tenant.tenantId === selectedTenantId) || availableTenants[0];
  const tenantAreas = areas.filter((area) => area.tenantId === selectedTenant?.tenantId);
  const tenantMemberships = memberships.filter((membership) => membership.tenantId === selectedTenant?.tenantId);
  const tenantScopedGroups = tenantGroups.filter((group) => group.tenantId === selectedTenant?.tenantId);
  const isGlobalAdmin = Boolean(currentUser?.isSuperuser);
  const canManage = isTenantAdmin(currentUser);

  const usersById = useMemo(() => new Map(users.map((user) => [String(user.id), user])), [users]);

  const loadData = useCallback(async () => {
    if (!canManage) return;
    setIsLoading(true);
    setError("");
    try {
      const [loadedUsers, loadedAreas, loadedMemberships, loadedGroups, loadedUserGroups] = await Promise.all([
        listUsers(authClient),
        listTenantAreas(authClient),
        listTenantMemberships(authClient),
        listTenantGroups(authClient),
        listTenantUserGroups(authClient),
      ]);
      setUsers(loadedUsers);
      setAreas(loadedAreas);
      setMemberships(loadedMemberships);
      setTenantGroups(loadedGroups);
      setTenantUserGroups(loadedUserGroups);

      if (isGlobalAdmin) {
        const loadedTenants = await listTenants(authClient);
        setTenants(loadedTenants);
        if (!selectedTenantId && loadedTenants[0]) setSelectedTenantId(loadedTenants[0].tenantId);
      } else if (!selectedTenantId && fallbackTenant) {
        setSelectedTenantId(fallbackTenant.tenantId);
      }
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar la administracion.");
    } finally {
      setIsLoading(false);
    }
  }, [authClient, canManage, fallbackTenant, isGlobalAdmin, selectedTenantId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function runSave(action, message) {
    setIsSaving(true);
    setError("");
    setSuccess("");
    try {
      await action();
      setSuccess(message);
      await loadData();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el cambio.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCreateTenant(event) {
    event.preventDefault();
    await runSave(async () => {
      const tenant = await createTenant(authClient, tenantForm);
      setTenantForm({ name: "", taxId: "" });
      setSelectedTenantId(tenant.tenantId);
    }, "Empresa creada correctamente.");
  }

  async function handleCreateArea(event) {
    event.preventDefault();
    await runSave(async () => {
      await createTenantArea(authClient, {
        tenantId: selectedTenant.tenantId,
        name: areaForm.name,
        parentAreaId: areaForm.parentAreaId,
      });
      setAreaForm({ name: "", parentAreaId: "" });
    }, "Area creada correctamente.");
  }

  async function handleCreateUser(event) {
    event.preventDefault();
    await runSave(async () => {
      await provisionTenantUser(authClient, {
        ...userForm,
        tenantId: selectedTenant.tenantId,
      });
      setUserForm({ username: "", email: "", firstName: "", lastName: "", password: "", role: "USER", areaId: "" });
    }, "Usuario creado y asignado a la empresa.");
  }

  async function handleSaveGroup(event) {
    event.preventDefault();
    await runSave(async () => {
      if (groupForm.groupId) {
        await updateTenantGroup(authClient, groupForm.groupId, groupForm);
      } else {
        await createTenantGroup(authClient, { ...groupForm, tenantId: selectedTenant.tenantId });
      }
      setGroupForm({ groupId: "", name: "Usuarios", description: "", permissions: ["view_documents", "download_documents"] });
    }, "Grupo y permisos guardados.");
  }

  async function handleAssignGroup(event) {
    event.preventDefault();
    await runSave(async () => {
      await assignTenantUserGroup(authClient, {
        tenantId: selectedTenant.tenantId,
        userId: assignGroupForm.userId,
        groupId: assignGroupForm.groupId,
      });
      setAssignGroupForm({ userId: "", groupId: "" });
    }, "Grupo asignado al usuario.");
  }

  function togglePermission(permission) {
    setGroupForm((current) => {
      const enabled = current.permissions.includes(permission);
      return {
        ...current,
        permissions: enabled
          ? current.permissions.filter((item) => item !== permission)
          : [...current.permissions, permission],
      };
    });
  }

  if (!canManage) {
    return null;
  }

  return (
    <AppShell
      sidebarOpen={sidebarOpen}
      sidebar={
        <Sidebar
          collapsed={!sidebarOpen}
          activeRoute={appRoutes.admin}
          onClose={() => setSidebarOpen(false)}
          onOpen={() => setSidebarOpen(true)}
          onLogout={logout}
          onNavigate={onNavigate}
          user={currentUser}
        />
      }
    >
      <main className="admin-screen">
        <div className="admin-container">
          <header className="admin-page-title">
            <IconButton className="admin-menu-button" onClick={() => setSidebarOpen((open) => !open)} aria-label="Menu">
              <Menu size={18} />
            </IconButton>
            <div>
              <h1>Administracion</h1>
              <p>Gestiona empresas, areas, usuarios, grupos y permisos con el mismo estilo del perfil.</p>
            </div>
          </header>

          <section className="admin-content">
            {error && (
              <div className="admin-alert error">
                <CircleAlert size={17} />
                {error}
              </div>
            )}
            {success && (
              <div className="admin-alert success">
                <Check size={17} />
                {success}
              </div>
            )}

            {isLoading ? (
              <div className="admin-loading">
                <Loader2 className="animate-spin" size={28} />
                Cargando administracion...
              </div>
            ) : (
              <>
                <div className="admin-tenant-bar">
                  <label>
                    Empresa activa
                    <select value={selectedTenant?.tenantId || ""} onChange={(event) => setSelectedTenantId(event.target.value)}>
                      {availableTenants.map((tenant) => (
                        <option key={tenant.tenantId} value={tenant.tenantId}>
                          {tenant.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="admin-tenant-meta">
                    <strong>{selectedTenant?.name || "Sin empresa"}</strong>
                    <span>{selectedTenant?.tenantId || "Crea o selecciona un tenant"}</span>
                  </div>
                </div>

                <div className="admin-grid">
                  {isGlobalAdmin && (
                    <AdminPanel icon={Building2} title="Crear empresa" subtitle="Alta global fuera del tenant activo." featured>
                      <form className="admin-form" onSubmit={handleCreateTenant}>
                        <label>
                          Nombre de empresa
                          <div className="admin-input-with-icon">
                            <Building2 size={16} />
                            <input value={tenantForm.name} onChange={(event) => setTenantForm({ ...tenantForm, name: event.target.value })} placeholder="Ej: Equipo Documental" required />
                          </div>
                        </label>
                        <label>
                          RUT / Tax ID
                          <div className="admin-input-with-icon">
                            <Hash size={16} />
                            <input value={tenantForm.taxId} onChange={(event) => setTenantForm({ ...tenantForm, taxId: event.target.value })} placeholder="Identificador tributario" />
                          </div>
                        </label>
                        <div className="admin-form-actions">
                          <button className="action-button-primary" type="submit" disabled={isSaving}>
                            <Save size={15} /> Crear empresa
                          </button>
                        </div>
                      </form>
                    </AdminPanel>
                  )}

                  <AdminPanel icon={FolderTree} title="Areas" subtitle="Estructura interna de la empresa.">
                    <form className="admin-form" onSubmit={handleCreateArea}>
                      <label>
                        Nombre del area
                        <input value={areaForm.name} onChange={(event) => setAreaForm({ ...areaForm, name: event.target.value })} placeholder="Ej: Operaciones" required />
                      </label>
                      <label>
                        Area padre
                        <select value={areaForm.parentAreaId} onChange={(event) => setAreaForm({ ...areaForm, parentAreaId: event.target.value })}>
                          <option value="">Sin area padre</option>
                          {tenantAreas.map((area) => (
                            <option key={area.areaId} value={area.areaId}>
                              {area.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="admin-form-actions">
                        <button className="action-button-primary" type="submit" disabled={isSaving || !selectedTenant}>
                          <Save size={15} /> Crear area
                        </button>
                      </div>
                    </form>
                    <CompactList items={tenantAreas.map((area) => ({ id: area.areaId, title: area.name, detail: area.parentAreaId ? "Subarea" : "Area raiz" }))} empty="Sin areas creadas." />
                  </AdminPanel>

                  <AdminPanel icon={UserPlus} title="Usuarios" subtitle="Crea usuarios y asignales area/rol tenant.">
                    <form className="admin-form" onSubmit={handleCreateUser}>
                      <div className="admin-two-cols">
                        <label>
                          Usuario
                          <input value={userForm.username} onChange={(event) => setUserForm({ ...userForm, username: event.target.value })} placeholder="nombre.usuario" required />
                        </label>
                        <label>
                          Correo
                          <input value={userForm.email} onChange={(event) => setUserForm({ ...userForm, email: event.target.value })} placeholder="correo@empresa.cl" type="email" />
                        </label>
                      </div>
                      <div className="admin-two-cols">
                        <label>
                          Nombre
                          <input value={userForm.firstName} onChange={(event) => setUserForm({ ...userForm, firstName: event.target.value })} placeholder="Nombre" />
                        </label>
                        <label>
                          Apellido
                          <input value={userForm.lastName} onChange={(event) => setUserForm({ ...userForm, lastName: event.target.value })} placeholder="Apellido" />
                        </label>
                      </div>
                      <label>
                        Password inicial
                        <input value={userForm.password} onChange={(event) => setUserForm({ ...userForm, password: event.target.value })} placeholder="Password inicial" type="password" required />
                      </label>
                      <div className="admin-two-cols">
                        <label>
                          Rol
                          <select value={userForm.role} onChange={(event) => setUserForm({ ...userForm, role: event.target.value })}>
                            {ROLE_OPTIONS.map((role) => (
                              <option key={role.value} value={role.value}>{role.label}</option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Area
                          <select value={userForm.areaId} onChange={(event) => setUserForm({ ...userForm, areaId: event.target.value })}>
                            <option value="">Sin area</option>
                            {tenantAreas.map((area) => (
                              <option key={area.areaId} value={area.areaId}>{area.name}</option>
                            ))}
                          </select>
                        </label>
                      </div>
                      <div className="admin-form-actions">
                        <button className="action-button-primary" type="submit" disabled={isSaving || !selectedTenant}>
                          <UserPlus size={15} /> Crear usuario
                        </button>
                      </div>
                    </form>
                  </AdminPanel>

                  <AdminPanel icon={ShieldCheck} title="Grupos y permisos" subtitle="Permisos finos gestionables por admin de empresa.">
                    <form className="admin-form" onSubmit={handleSaveGroup}>
                      <label>
                        Grupo
                        <select
                          value={groupForm.groupId}
                          onChange={(event) => {
                            const group = tenantScopedGroups.find((item) => item.groupId === event.target.value);
                            setGroupForm(
                              group
                                ? { groupId: group.groupId, name: group.name, description: group.description, permissions: group.permissions }
                                : { groupId: "", name: "", description: "", permissions: [] },
                            );
                          }}
                        >
                          <option value="">Nuevo grupo</option>
                          {tenantScopedGroups.map((group) => (
                            <option key={group.groupId} value={group.groupId}>{group.name}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Nombre del grupo
                        <input value={groupForm.name} onChange={(event) => setGroupForm({ ...groupForm, name: event.target.value })} placeholder="Nombre del grupo" required />
                      </label>
                      <label>
                        Descripcion
                        <input value={groupForm.description} onChange={(event) => setGroupForm({ ...groupForm, description: event.target.value })} placeholder="Descripcion" />
                      </label>
                      <div className="permission-picker" aria-label="Permisos del grupo">
                        {TENANT_PERMISSION_OPTIONS.map((permission) => (
                          <button
                            key={permission}
                            className={groupForm.permissions.includes(permission) ? "active" : ""}
                            type="button"
                            onClick={() => togglePermission(permission)}
                          >
                            {groupForm.permissions.includes(permission) && <Check size={13} />}
                            {PERMISSION_LABELS[permission] || permission}
                          </button>
                        ))}
                      </div>
                      <div className="admin-form-actions">
                        <button className="action-button-primary" type="submit" disabled={isSaving || !selectedTenant}>
                          <KeyRound size={15} /> Guardar grupo
                        </button>
                      </div>
                    </form>
                  </AdminPanel>

                  <AdminPanel icon={UsersRound} title="Asignar grupos" subtitle="Relaciona usuarios con grupos operativos.">
                    <form className="admin-form" onSubmit={handleAssignGroup}>
                      <label>
                        Usuario
                        <select value={assignGroupForm.userId} onChange={(event) => setAssignGroupForm({ ...assignGroupForm, userId: event.target.value })} required>
                          <option value="">Selecciona usuario</option>
                          {tenantMemberships.map((membership) => {
                            const user = usersById.get(membership.userId);
                            return (
                              <option key={membership.membershipId} value={membership.userId}>
                                {user?.username || membership.userId} - {membership.role}
                              </option>
                            );
                          })}
                        </select>
                      </label>
                      <label>
                        Grupo
                        <select value={assignGroupForm.groupId} onChange={(event) => setAssignGroupForm({ ...assignGroupForm, groupId: event.target.value })} required>
                          <option value="">Selecciona grupo</option>
                          {tenantScopedGroups.map((group) => (
                            <option key={group.groupId} value={group.groupId}>{group.name}</option>
                          ))}
                        </select>
                      </label>
                      <div className="admin-form-actions">
                        <button className="action-button-primary" type="submit" disabled={isSaving}>
                          <UsersRound size={15} /> Asignar grupo
                        </button>
                      </div>
                    </form>
                    <CompactList
                      items={tenantUserGroups
                        .filter((row) => row.tenantId === selectedTenant?.tenantId)
                        .map((row) => ({
                          id: `${row.userId}-${row.groupId}`,
                          title: usersById.get(row.userId)?.username || row.userId,
                          detail: row.groupName,
                        }))}
                      empty="Sin grupos asignados."
                    />
                  </AdminPanel>
                </div>
              </>
            )}
          </section>
        </div>
      </main>
    </AppShell>
  );
}

function AdminPanel({ children, featured = false, icon: Icon, title, subtitle }) {
  return (
    <article className={`admin-panel ${featured ? "featured" : ""}`}>
      <header className="admin-panel-header">
        <span>
          <Icon size={18} />
        </span>
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
      </header>
      {children}
    </article>
  );
}

function CompactList({ items, empty }) {
  if (!items.length) return <p className="admin-empty">{empty}</p>;
  return (
    <div className="admin-compact-list">
      {items.slice(0, 8).map((item) => (
        <div key={item.id}>
          <strong>{item.title}</strong>
          <span>{item.detail}</span>
        </div>
      ))}
    </div>
  );
}

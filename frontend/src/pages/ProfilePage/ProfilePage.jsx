import { useState, useEffect } from "react";
import { 
  ArrowLeft, 
  Save, 
  User, 
  Mail, 
  Phone, 
  Image as ImageIcon, 
  Globe, 
  Shield, 
  Loader2, 
  CheckCircle2, 
  AlertCircle,
  UploadCloud,
  Lock,
  MapPin,
  Briefcase,
  Building,
  Info,
  Check,
  X,
  KeyRound
} from "lucide-react";

import { useAuthContext } from "../../app/providers/AuthProvider";
import { appRoutes } from "../../app/router/routes";
import { AppShell } from "../../shared/layouts/AppShell";
import { Sidebar } from "../../widgets/Sidebar/Sidebar";
import { useProfile } from "../../features/profile/hooks/useProfile";
import { uploadProfilePicture } from "../../features/profile/api/profile.api";
import { changePassword } from "../../features/auth/api/user-management.api";
import "./ProfilePage.css";

export function ProfilePage({ onNavigate }) {
  const { currentUser, logout, profileClient, authClient, setProfile: setGlobalProfile } = useAuthContext();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState(() => {
    const requestedTab = sessionStorage.getItem("blandskron:profile-tab");
    sessionStorage.removeItem("blandskron:profile-tab");
    return requestedTab || "personal";
  }); // "personal" | "security" | "permissions"

  // Personal Info Form local state
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [profilePictureUrl, setProfilePictureUrl] = useState("");
  const [location, setLocation] = useState("");
  const [position, setPosition] = useState("");
  const [department, setDepartment] = useState("");
  const [preferredLanguage, setPreferredLanguage] = useState("es");
  const [bio, setBio] = useState("");

  // Security / Change Password Form local state
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);

  // Hook to connect with ProfileServices microservice
  const {
    profile,
    isLoading,
    error,
    isSaving,
    saveSuccess,
    save,
    clearSuccess,
    isConflict,
    reload,
  } = useProfile(profileClient, (updatedData) => {
    // Callback: update the global auth context profile state
    setGlobalProfile(updatedData);
  });

  // Populate local form fields when backend profile is loaded
  useEffect(() => {
    if (profile) {
      setEmail(profile.profile_id ? (profile.email ?? "") : (currentUser?.email || ""));
      setPhoneNumber(profile.phone_number || "");
      setProfilePictureUrl(profile.profile_picture_url || "");
      
      const extra = profile.additional_info || {};
      const textField = (name, fallback = "") => typeof extra[name] === "string" ? extra[name] : fallback;
      setFullName(textField("full_name", currentUser?.displayName || ""));
      setLocation(textField("location"));
      setPosition(textField("position"));
      setDepartment(textField("department"));
      setPreferredLanguage(textField("preferred_language", "es"));
      setBio(textField("bio"));
    }
  }, [profile, currentUser]);

  // Compute initials for avatar preview fallback
  const initials = (fullName || currentUser?.displayName || currentUser?.username || "U")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  // Local state for file upload
  const [uploadingFile, setUploadingFile] = useState(false);
  const [uploadError, setUploadError] = useState("");

  async function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      setUploadError("Por favor selecciona un archivo de imagen válido.");
      return;
    }

    const maxSize = 5 * 1024 * 1024;
    if (file.size > maxSize) {
      setUploadError("La imagen supera el límite de 5MB.");
      return;
    }

    try {
      setUploadingFile(true);
      setUploadError("");
      clearSuccess();

      const response = await uploadProfilePicture(profileClient, file);
      if (response && response.url) {
        setProfilePictureUrl(response.url);
      } else {
        throw new Error("No se pudo obtener la URL de la imagen.");
      }
    } catch (err) {
      console.error("Error al subir archivo:", err);
      setUploadError(err.message || "Error al subir la imagen.");
    } finally {
      setUploadingFile(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    clearSuccess();

    const payload = {
      email,
      phone_number: phoneNumber,
      profile_picture_url: profilePictureUrl,
      additional_info: {
        ...profile?.additional_info,
        full_name: fullName,
        location,
        position,
        department,
        preferred_language: preferredLanguage,
        bio,
      }
    };

    await save(payload);
  }

  async function handlePasswordChange(e) {
    e.preventDefault();
    setPasswordError("");
    setPasswordSuccess("");

    if (!oldPassword || !newPassword || !confirmPassword) {
      setPasswordError("Todos los campos de contraseña son requeridos.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError("Las contraseñas no coinciden.");
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError("La contraseña debe tener al menos 8 caracteres.");
      return;
    }

    try {
      setChangingPassword(true);
      await changePassword(authClient, oldPassword, newPassword);
      setPasswordSuccess("Contraseña actualizada exitosamente.");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      console.error("Error al cambiar contraseña:", err);
      setPasswordError(err.message || "No se pudo actualizar la contraseña. Verifica tu contraseña actual.");
    } finally {
      setChangingPassword(false);
    }
  }

  function handleCancel() {
    onNavigate?.(appRoutes.chat);
  }

  const permissionModules = [
    {
      id: "chat",
      name: "Asistente y Chat IA",
      description: "Consultas al bot inteligente, creación de prompts semánticos y bases de datos conversacionales.",
      keywords: ["chat", "conversation", "ragchat"],
    },
    {
      id: "documents",
      name: "Gestión Documental",
      description: "Carga masiva, procesamiento OCR, búsquedas vectoriales avanzadas y biblioteca central.",
      keywords: ["document", "documentlibrary", "documentaccess", "document_library", "file"],
    },
    {
      id: "users",
      name: "Perfil y acceso",
      description: "Datos de usuario, grupos de seguridad y permisos de acceso.",
      keywords: ["user", "profile", "group", "permission"],
    },
  ];

  const hasModulePermission = (keywords, action) => {
    if (currentUser?.isSuperuser || currentUser?.isStaff || profile?.is_superuser) {
      return true;
    }

    const perms = profile?.permissions || currentUser?.permissions || [];
    if (perms.length === 0) return false;

    let actionIdentifiers = [];
    if (action === "view") actionIdentifiers = ["view", "read", "get"];
    else if (action === "add") actionIdentifiers = ["add", "create", "post"];
    else if (action === "change") actionIdentifiers = ["change", "edit", "update", "patch", "put"];
    else if (action === "delete") actionIdentifiers = ["delete", "remove", "destroy"];

    return perms.some((perm) => {
      const lowerPerm = perm.toLowerCase();
      const matchesKeyword = keywords.some((keyword) => lowerPerm.includes(keyword.toLowerCase()));
      const matchesAction = actionIdentifiers.some((act) => lowerPerm.includes(act));
      return matchesKeyword && matchesAction;
    });
  };

  return (
    <AppShell
      sidebarOpen={sidebarOpen}
      sidebar={
        <Sidebar
          collapsed={!sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onOpen={() => setSidebarOpen(true)}
          onLogout={logout}
          onNavigate={onNavigate}
          activeRoute={appRoutes.profile}
          user={currentUser}
        />
      }
    >
      <main className="profile-screen">
        <div className="profile-container">
          <div className="profile-page-title" style={{ marginBottom: "24px" }}>
            <h2 style={{ fontSize: "24px", fontWeight: "700", margin: 0 }}>Mi Perfil</h2>
            <p style={{ color: "var(--muted)", fontSize: "14px", margin: "4px 0 0" }}>Configura tu cuenta y revisa tus accesos asignados</p>
          </div>
          <div className="profile-layout-wrapper">
            {/* Tabs Navigation Bar */}
            <div className="profile-tabs-nav">
              <button 
                type="button"
                className={`profile-tab-link ${activeTab === "personal" ? "active" : ""}`}
                onClick={() => { setActiveTab("personal"); clearSuccess(); }}
              >
                <User size={16} />
                Información Personal
              </button>
              <button 
                type="button"
                className={`profile-tab-link ${activeTab === "security" ? "active" : ""}`}
                onClick={() => { setActiveTab("security"); setPasswordError(""); setPasswordSuccess(""); }}
              >
                <Lock size={16} />
                Seguridad
              </button>
              <button 
                type="button"
                className={`profile-tab-link ${activeTab === "permissions" ? "active" : ""}`}
                onClick={() => setActiveTab("permissions")}
              >
                <Shield size={16} />
                Permisos y Accesos
              </button>
            </div>

            {isLoading || !profile ? (
              <div className="profile-loader-box">
                {isLoading && <Loader2 className="animate-spin" size={32} />}
                <p role={error ? "alert" : undefined}>{error || "Cargando información del perfil..."}</p>
                {error && <button type="button" onClick={reload} disabled={!profileClient}>Volver a cargar perfil</button>}
              </div>
            ) : (
              <div className="profile-tab-content">
                {/* TAB 1: INFORMACION PERSONAL */}
                {activeTab === "personal" && (
                  <div className="profile-tab-pane">
                    <div className="profile-card">
                      <div className="profile-card-header">
                        <h3>Datos Personales</h3>
                        <p>Actualiza la información visible y de contacto de tu perfil</p>
                      </div>

                      {error && (
                        <div className="alert-message alert-error">
                          <AlertCircle size={18} />
                          <span>{error}</span>
                          {isConflict && (
                            <button type="button" onClick={reload} disabled={isSaving}>
                              Descartar cambios y recargar perfil
                            </button>
                          )}
                        </div>
                      )}

                      {saveSuccess && (
                        <div className="alert-message alert-success">
                          <CheckCircle2 size={18} />
                          <span>¡Perfil actualizado correctamente!</span>
                        </div>
                      )}

                      <form onSubmit={handleSubmit} className="profile-form">
                        <div className="avatar-upload-block">
                          <div className="avatar-preview-outer">
                            {profilePictureUrl ? (
                              <img 
                                src={profilePictureUrl} 
                                alt="Foto de perfil" 
                                className="avatar-preview-img"
                                onError={(e) => {
                                  e.target.style.display = "none";
                                  e.target.parentNode.innerHTML = `<span className="avatar-fallback-initials">${initials}</span>`;
                                }}
                              />
                            ) : (
                              <span className="avatar-fallback-initials">{initials}</span>
                            )}
                          </div>
                          <div className="avatar-upload-actions">
                            <h4>Foto de Perfil</h4>
                            <p>Formatos recomendados: JPG o PNG. Tamaño máximo: 5MB.</p>
                            <div className="avatar-upload-buttons">
                              <label className="btn-file-upload">
                                {uploadingFile ? (
                                  <>
                                    <Loader2 className="animate-spin" size={14} />
                                    Subiendo...
                                  </>
                                ) : (
                                  <>
                                    <UploadCloud size={14} />
                                    Subir nueva imagen
                                  </>
                                )}
                                <input 
                                  type="file" 
                                  accept="image/*" 
                                  style={{ display: "none" }} 
                                  disabled={uploadingFile || isSaving}
                                  onChange={handleFileUpload}
                                />
                              </label>
                              {uploadError && <span className="upload-error-msg">{uploadError}</span>}
                            </div>
                          </div>
                        </div>

                        <div className="profile-form-grid">
                          <div className="profile-form-group">
                            <label htmlFor="fullName">Nombre Completo</label>
                            <div className="input-with-icon">
                              <User size={16} className="input-icon" />
                              <input 
                                id="fullName" maxLength={120}
                                type="text" 
                                className="profile-input" 
                                value={fullName}
                                onChange={(e) => {
                                  setFullName(e.target.value);
                                  clearSuccess();
                                }}
                                placeholder="Ingresa tu nombre completo"
                                disabled={isSaving}
                                required
                              />
                            </div>
                          </div>

                          <div className="profile-form-group">
                            <label htmlFor="email">Correo Electrónico (No editable)</label>
                            <div className="input-with-icon">
                              <Mail size={16} className="input-icon" />
                              <input 
                                id="email" maxLength={254}
                                type="email" 
                                className="profile-input" 
                                value={email}
                                disabled
                              />
                            </div>
                          </div>

                          <div className="profile-form-grid-2col">
                            <div className="profile-form-group">
                              <label htmlFor="phone">Número de Teléfono</label>
                              <div className="input-with-icon">
                                <Phone size={16} className="input-icon" />
                                <input 
                                  id="phone" maxLength={32}
                                  type="text" 
                                  className="profile-input" 
                                  value={phoneNumber}
                                  onChange={(e) => {
                                    setPhoneNumber(e.target.value);
                                    clearSuccess();
                                  }}
                                  placeholder="Ej: +56 9 1234 5678"
                                  disabled={isSaving}
                                />
                              </div>
                            </div>

                            <div className="profile-form-group">
                              <label htmlFor="location">Ubicación / Oficina</label>
                              <div className="input-with-icon">
                                <MapPin size={16} className="input-icon" />
                                <input 
                                  id="location" maxLength={120}
                                  type="text" 
                                  className="profile-input" 
                                  value={location}
                                  onChange={(e) => {
                                    setLocation(e.target.value);
                                    clearSuccess();
                                  }}
                                  placeholder="Ciudad, País o Sucursal"
                                  disabled={isSaving}
                                />
                              </div>
                            </div>
                          </div>

                          <div className="profile-form-grid-2col">
                            <div className="profile-form-group">
                              <label htmlFor="position">Cargo / Puesto</label>
                              <div className="input-with-icon">
                                <Briefcase size={16} className="input-icon" />
                                <input 
                                  id="position" maxLength={120}
                                  type="text" 
                                  className="profile-input" 
                                  value={position}
                                  onChange={(e) => {
                                    setPosition(e.target.value);
                                    clearSuccess();
                                  }}
                                  placeholder="Ej: Analista de Negocios"
                                  disabled={isSaving}
                                />
                              </div>
                            </div>

                            <div className="profile-form-group">
                              <label htmlFor="department">Departamento / Área</label>
                              <div className="input-with-icon">
                                <Building size={16} className="input-icon" />
                                <input 
                                  id="department" maxLength={120}
                                  type="text" 
                                  className="profile-input" 
                                  value={department}
                                  onChange={(e) => {
                                    setDepartment(e.target.value);
                                    clearSuccess();
                                  }}
                                  placeholder="Ej: Legal, Operaciones"
                                  disabled={isSaving}
                                />
                              </div>
                            </div>
                          </div>

                          <div className="profile-form-group">
                            <label htmlFor="avatar-url">URL de Imagen de Perfil (Opcional)</label>
                            <div className="input-with-icon">
                              <ImageIcon size={16} className="input-icon" />
                              <input 
                                id="avatar-url" maxLength={2048}
                                type="url" 
                                className="profile-input" 
                                value={profilePictureUrl}
                                onChange={(e) => {
                                  setProfilePictureUrl(e.target.value);
                                  clearSuccess();
                                }}
                                placeholder="https://ejemplo.com/mi-avatar.png"
                                disabled={isSaving}
                              />
                            </div>
                          </div>

                          <div className="profile-form-group">
                            <label htmlFor="language">Idioma Preferido</label>
                            <div className="input-with-icon">
                              <Globe size={16} className="input-icon" />
                              <select
                                id="language"
                                className="profile-input"
                                value={preferredLanguage}
                                onChange={(e) => {
                                  setPreferredLanguage(e.target.value);
                                  clearSuccess();
                                }}
                                disabled={isSaving}
                                style={{ paddingRight: "24px" }}
                              >
                                <option value="es">Español (ES)</option>
                                <option value="en">English (EN)</option>
                              </select>
                            </div>
                          </div>

                          <div className="profile-form-group">
                            <label htmlFor="bio">Biografía / Acerca de mí</label>
                            <textarea 
                              id="bio" maxLength={2000}
                              className="profile-textarea" 
                              value={bio}
                              onChange={(e) => {
                                setBio(e.target.value);
                                clearSuccess();
                              }}
                              placeholder="Escribe algo sobre ti, tu área de especialización o notas del perfil..."
                              disabled={isSaving}
                            />
                          </div>
                        </div>

                        <div className="profile-form-actions">
                          <button 
                            type="button" 
                            className="btn-flat-secondary" 
                            onClick={handleCancel}
                            disabled={isSaving}
                          >
                            Cancelar
                          </button>
                          <button 
                            type="submit" 
                            className="btn-flat-primary"
                            disabled={isSaving}
                          >
                            {isSaving ? (
                              <>
                                <Loader2 className="animate-spin" size={15} />
                                Guardando...
                              </>
                            ) : (
                              <>
                                <Save size={15} />
                                Guardar cambios
                              </>
                            )}
                          </button>
                        </div>
                      </form>
                    </div>
                  </div>
                )}

                {/* TAB 2: SEGURIDAD Y CONTRASENA */}
                {activeTab === "security" && (
                  <div className="profile-tab-pane security-tab-grid">
                    {/* Form Block */}
                    <div className="profile-card">
                      <div className="profile-card-header">
                        <h3>Cambiar Contraseña</h3>
                        <p>Actualiza tu contraseña periódicamente para mantener tu cuenta segura</p>
                      </div>

                      {passwordError && (
                        <div className="alert-message alert-error">
                          <AlertCircle size={18} />
                          <span>{passwordError}</span>
                        </div>
                      )}

                      {passwordSuccess && (
                        <div className="alert-message alert-success">
                          <CheckCircle2 size={18} />
                          <span>{passwordSuccess}</span>
                        </div>
                      )}

                      <form onSubmit={handlePasswordChange} className="profile-form">
                        <div className="profile-form-group">
                          <label htmlFor="oldPassword">Contraseña Actual</label>
                          <div className="input-with-icon">
                            <KeyRound size={16} className="input-icon" />
                            <input 
                              id="oldPassword"
                              type="password" 
                              className="profile-input" 
                              value={oldPassword}
                              onChange={(e) => setOldPassword(e.target.value)}
                              placeholder="Escribe tu contraseña actual"
                              disabled={changingPassword}
                              required
                            />
                          </div>
                        </div>

                        <div className="profile-form-group">
                          <label htmlFor="newPassword">Nueva Contraseña</label>
                          <div className="input-with-icon">
                            <Lock size={16} className="input-icon" />
                            <input 
                              id="newPassword"
                              type="password" 
                              className="profile-input" 
                              value={newPassword}
                              onChange={(e) => setNewPassword(e.target.value)}
                              placeholder="Nueva contraseña (mínimo 8 caracteres)"
                              disabled={changingPassword}
                              required
                            />
                          </div>
                        </div>

                        <div className="profile-form-group">
                          <label htmlFor="confirmPassword">Confirmar Nueva Contraseña</label>
                          <div className="input-with-icon">
                            <Lock size={16} className="input-icon" />
                            <input 
                              id="confirmPassword"
                              type="password" 
                              className="profile-input" 
                              value={confirmPassword}
                              onChange={(e) => setConfirmPassword(e.target.value)}
                              placeholder="Reescribe tu nueva contraseña"
                              disabled={changingPassword}
                              required
                            />
                          </div>
                        </div>

                        <div className="profile-form-actions">
                          <button 
                            type="submit" 
                            className="btn-flat-primary"
                            disabled={changingPassword}
                            style={{ width: "100%" }}
                          >
                            {changingPassword ? (
                              <>
                                <Loader2 className="animate-spin" size={15} />
                                Cambiando contraseña...
                              </>
                            ) : (
                              "Actualizar contraseña"
                            )}
                          </button>
                        </div>
                      </form>
                    </div>

                    {/* Recommendations Block */}
                    <div className="profile-card recommendations-card">
                      <div className="profile-card-header">
                        <h3>Recomendaciones de Seguridad</h3>
                        <p>Sigue estos lineamientos para mantener tu información a salvo</p>
                      </div>
                      
                      <ul className="security-guidelines-list">
                        <li>
                          <span className="dot"></span>
                          <div>
                            <strong>Longitud robusta</strong>
                            <p>Tu contraseña debe tener al menos 8 caracteres de largo. Mientras más larga, mejor.</p>
                          </div>
                        </li>
                        <li>
                          <span className="dot"></span>
                          <div>
                            <strong>Combina caracteres</strong>
                            <p>Usa una mezcla de letras mayúsculas, minúsculas, números y símbolos especiales (como @, #, $, %).</p>
                          </div>
                        </li>
                        <li>
                          <span className="dot"></span>
                          <div>
                            <strong>Evita información personal</strong>
                            <p>No uses nombres de familiares, mascotas, fechas de nacimiento o palabras obvias.</p>
                          </div>
                        </li>
                        <li>
                          <span className="dot"></span>
                          <div>
                            <strong>Contraseña única</strong>
                            <p>No reutilices la contraseña que usas para esta plataforma en otros servicios web externos.</p>
                          </div>
                        </li>
                      </ul>
                    </div>
                  </div>
                )}

                {/* TAB 3: PERMISOS Y ACCESOS */}
                {activeTab === "permissions" && (
                  <div className="profile-tab-pane permissions-tab-pane">
                    <div className="alert-message alert-info">
                      <Info size={18} />
                      <span>
                        Los roles, grupos y permisos de acceso son de <strong>lectura exclusiva</strong>. Para solicitar modificaciones o accesos adicionales, ponte en contacto con el administrador de IT de tu organización.
                      </span>
                    </div>

                    <div className="permissions-grid-container">
                      {/* Groups Card */}
                      <div className="profile-card groups-overview-card">
                        <div className="profile-card-header">
                          <h3>Grupos y Roles</h3>
                          <p>Grupos organizacionales asignados a tu cuenta</p>
                        </div>

                        <div className="assigned-groups-tags">
                          {profile?.groups && profile.groups.length > 0 ? (
                            profile.groups.map((groupName, i) => (
                              <span key={i} className="group-tag">
                                {groupName}
                              </span>
                            ))
                          ) : (
                            <div className="empty-info-msg">
                              No tienes grupos organizacionales específicos asignados.
                            </div>
                          )}
                        </div>

                        <div className="superuser-status-badge-container">
                          {(currentUser?.isSuperuser || profile?.is_superuser) && (
                            <div className="superuser-badge">
                              <Shield size={16} />
                              Superusuario del Sistema
                            </div>
                          )}
                          {currentUser?.isStaff && (
                            <div className="staff-badge">
                              <Shield size={16} />
                              Personal de Administración (Staff)
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Modular Matrix Card */}
                      <div className="profile-card permissions-matrix-card">
                        <div className="profile-card-header">
                          <h3>Módulos del Sistema y Permisos</h3>
                          <p>Verifica tu capacidad de lectura, escritura y borrado en cada módulo principal</p>
                        </div>

                        <div className="modules-permissions-list">
                          {permissionModules.map((module) => {
                            const readActive = hasModulePermission(module.keywords, "view");
                            const createActive = hasModulePermission(module.keywords, "add");
                            const editActive = hasModulePermission(module.keywords, "change");
                            const deleteActive = hasModulePermission(module.keywords, "delete");

                            return (
                              <div key={module.id} className="module-permission-row">
                                <div className="module-permission-info">
                                  <h4>{module.name}</h4>
                                  <p>{module.description}</p>
                                </div>
                                <div className="module-permission-chips">
                                  <span className={`perm-chip ${readActive ? "active" : "inactive"}`}>
                                    {readActive ? <Check size={12} /> : <X size={12} />}
                                    Lectura
                                  </span>
                                  <span className={`perm-chip ${createActive ? "active" : "inactive"}`}>
                                    {createActive ? <Check size={12} /> : <X size={12} />}
                                    Creación
                                  </span>
                                  <span className={`perm-chip ${editActive ? "active" : "inactive"}`}>
                                    {editActive ? <Check size={12} /> : <X size={12} />}
                                    Edición
                                  </span>
                                  <span className={`perm-chip ${deleteActive ? "active" : "inactive"}`}>
                                    {deleteActive ? <Check size={12} /> : <X size={12} />}
                                    Eliminación
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </AppShell>
  );
}

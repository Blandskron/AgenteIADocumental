import { useState, useEffect, useRef } from "react";
import {
  Save,
  User,
  Mail,
  Phone,
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
  KeyRound
} from "lucide-react";

import { useAuthContext } from "../../app/providers/AuthProvider";
import { appRoutes } from "../../app/router/routes";
import { AppShell } from "../../shared/layouts/AppShell";
import { Sidebar } from "../../widgets/Sidebar/Sidebar";
import { useProfile } from "../../features/profile/hooks/useProfile";
import { usePrivateAvatar } from "../../features/profile/hooks/usePrivateAvatar";
import { changePassword } from "../../features/auth/api/user-management.api";
import { ProfilePermissions } from "../../features/profile/components/ProfilePermissions";
import "./ProfilePage.css";

export function ProfilePage(props) {
  const { profileSessionKey } = useAuthContext();
  return <ProfileEditor key={profileSessionKey || "signed-out"} {...props} />;
}

function ProfileEditor({ onNavigate }) {
  const { currentUser, logout, profileClient, authClient, setProfile: setGlobalProfile } = useAuthContext();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const passwordPending = useRef(false);
  const passwordRequest = useRef(null);
  const avatarInput = useRef(null);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; passwordRequest.current?.abort(); }; }, []);
  const [activeTab, setActiveTab] = useState(() => {
    const requestedTab = sessionStorage.getItem("blandskron:profile-tab");
    sessionStorage.removeItem("blandskron:profile-tab");
    return ["personal", "security", "permissions"].includes(requestedTab) ? requestedTab : "personal";
  }); // "personal" | "security" | "permissions"

  // Personal Info Form local state
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
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
    formProfile,
    uploadAvatar,
    removeAvatar,
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

  const avatar = usePrivateAvatar(profileClient, profile?.profile_picture_url);
  // Avatar updates retain unsaved contact edits; only form snapshots repopulate fields.
  useEffect(() => {
    if (formProfile) {
      const profile = formProfile;
      setEmail(profile.email ?? "");
      setPhoneNumber(profile.phone_number || "");

      const extra = profile.additional_info || {};
      const textField = (name, fallback = "") => typeof extra[name] === "string" ? extra[name] : fallback;
      setFullName(textField("full_name", currentUser?.displayName || ""));
      setLocation(textField("location"));
      setPosition(textField("position"));
      setDepartment(textField("department"));
      setPreferredLanguage(textField("preferred_language", "es"));
      setBio(textField("bio"));
    }
  }, [formProfile]);

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
    e.target.value = "";
    if (!file) return;

    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
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

      await uploadAvatar(file);
    } catch (err) {
      if (mounted.current) setUploadError(err.message || "Error al subir la imagen.");
    } finally {
      if (mounted.current) setUploadingFile(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    clearSuccess();

    const payload = {
      email,
      phone_number: phoneNumber,
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
    if (passwordPending.current) return;
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
      passwordPending.current = true;
      passwordRequest.current = new AbortController();
      setChangingPassword(true);
      await changePassword(authClient, oldPassword, newPassword, passwordRequest.current.signal);
      if (!mounted.current) return;
      setPasswordSuccess("Contraseña actualizada. Vuelve a iniciar sesión con la nueva contraseña.");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      if (mounted.current) setPasswordError(err.message || "No se pudo actualizar la contraseña. Verifica tu contraseña actual.");
    } finally {
      passwordPending.current = false;
      passwordRequest.current = null;
      if (mounted.current) setChangingPassword(false);
    }
  }

  function handleCancel() {
    onNavigate?.(appRoutes.chat);
  }

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
            <div className="profile-tabs-nav" role="group" aria-label="Secciones del perfil">
              <button
                type="button"
                className={`profile-tab-link ${activeTab === "personal" ? "active" : ""}`}
                aria-pressed={activeTab === "personal"}
                onClick={() => { setActiveTab("personal"); clearSuccess(); }}
              >
                <User size={16} />
                Información Personal
              </button>
              <button
                type="button"
                className={`profile-tab-link ${activeTab === "security" ? "active" : ""}`}
                aria-pressed={activeTab === "security"}
                onClick={() => { setActiveTab("security"); setPasswordError(""); setPasswordSuccess(""); }}
              >
                <Lock size={16} />
                Seguridad
              </button>
              <button
                type="button"
                className={`profile-tab-link ${activeTab === "permissions" ? "active" : ""}`}
                aria-pressed={activeTab === "permissions"}
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
                        <div className="alert-message alert-error" role="alert">
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
                        <div className="alert-message alert-success" role="status">
                          <CheckCircle2 size={18} />
                          <span>¡Perfil actualizado correctamente!</span>
                        </div>
                      )}

                      <form onSubmit={handleSubmit} className="profile-form" aria-busy={isSaving}>
                        <div className="avatar-upload-block">
                          <div className="avatar-preview-outer">
                            {avatar.src ? (
                              <img
                                src={avatar.src}
                                alt="Foto de perfil"
                                className="avatar-preview-img"
                                onError={avatar.onError}
                              />
                            ) : (
                              <span className="avatar-fallback-initials">{initials}</span>
                            )}
                          </div>
                          <div className="avatar-upload-actions">
                            <h4>Foto de Perfil</h4>
                            <p>JPG, PNG o WebP sin animación; hasta 5 MiB. La foto se guarda al subirla y solo se muestra en tu sesión.</p>
                            <div className="avatar-upload-buttons">
                              <button type="button" className="btn-file-upload" disabled={uploadingFile || isSaving}
                                onClick={() => avatarInput.current?.click()}>
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
                              </button>
                                <input ref={avatarInput} aria-label="Seleccionar foto de perfil"
                                  type="file"
                                  accept="image/jpeg,image/png,image/webp"
                                  style={{ display: "none" }}
                                  disabled={uploadingFile || isSaving}
                                  onChange={handleFileUpload}
                                />
                              <button type="button" onClick={removeAvatar} disabled={isSaving || uploadingFile || !profile?.profile_picture_url}>Quitar foto</button>
                              {(uploadError || avatar.error) && <span role="alert" className="upload-error-msg">{uploadError || avatar.error}</span>}
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
                            <label htmlFor="email">Correo de contacto</label>
                            <div className="input-with-icon">
                              <Mail size={16} className="input-icon" />
                              <input
                                id="email" maxLength={254}
                                type="email"
                                className="profile-input"
                                value={email}
                                onChange={(e) => { setEmail(e.target.value); clearSuccess(); }}
                                disabled={isSaving}
                                aria-describedby="contact-email-help"
                              />
                            </div>
                            <p id="contact-email-help">No cambia tu usuario ni el correo de identidad: {currentUser?.email || "sin correo de identidad"}.</p>
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
                        <div className="alert-message alert-error" role="alert">
                          <AlertCircle size={18} />
                          <span>{passwordError}</span>
                        </div>
                      )}

                      {passwordSuccess && (
                        <div className="alert-message alert-success" role="status">
                          <CheckCircle2 size={18} />
                          <span>{passwordSuccess}</span>
                          <button type="button" onClick={logout}>Cerrar sesión para volver a ingresar</button>
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
                              autoComplete="current-password"
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
                              autoComplete="new-password"
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
                              autoComplete="new-password"
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
                  <div className="profile-tab-pane permissions-tab-pane"><ProfilePermissions user={currentUser} /></div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </AppShell>
  );
}

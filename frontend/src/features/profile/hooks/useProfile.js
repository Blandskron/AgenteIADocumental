import { useState, useEffect, useRef } from "react";
import { getProfile, updateProfile } from "../api/profile.api";

export function useProfile(profileClient, onProfileUpdated) {
  const [profile, setProfile] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [isConflict, setIsConflict] = useState(false);
  const activeClient = useRef(null);
  const generation = useRef(0);
  const saveInFlight = useRef(false);

  useEffect(() => {
    activeClient.current = profileClient;
    const currentGeneration = ++generation.current;
    setProfile(null);
    setIsSaving(false);
    setIsConflict(false);
    setSaveSuccess(false);
    saveInFlight.current = false;
    if (!profileClient) return;

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    getProfile(profileClient)
      .then((data) => {
        if (isMounted && currentGeneration === generation.current) {
          setProfile(data);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted && currentGeneration === generation.current) {
          setError(err.message || "No se pudo cargar el perfil.");
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
      activeClient.current = null;
    };
  }, [profileClient]);

  async function save(updatedData) {
    if (!profileClient || !profile || activeClient.current !== profileClient || saveInFlight.current) return false;
    saveInFlight.current = true;

    setIsSaving(true);
    setSaveSuccess(false);
    setError(null);

    try {
      const data = await updateProfile(profileClient, updatedData, profile?.version ?? 0);
      if (activeClient.current !== profileClient) return false;
      setProfile(data);
      setIsConflict(false);
      setSaveSuccess(true);
      if (onProfileUpdated) {
        onProfileUpdated(data);
      }
      return true;
    } catch (err) {
      if (activeClient.current !== profileClient) return false;
      setIsConflict(err.status === 409);
      setError(err.status === 409
        ? "El perfil cambió en otra sesión. Tus cambios siguen en el formulario; recarga el perfil antes de volver a guardar."
        : err.message || "No se pudo guardar el perfil.");
      return false;
    } finally {
      if (activeClient.current === profileClient) {
        saveInFlight.current = false;
        setIsSaving(false);
      }
    }
  }

  function clearSuccess() {
    setSaveSuccess(false);
  }

  async function reload() {
    if (!profileClient || saveInFlight.current || activeClient.current !== profileClient) return;
    const currentGeneration = ++generation.current;
    setIsLoading(true);
    try {
      const data = await getProfile(profileClient);
      if (activeClient.current !== profileClient || currentGeneration !== generation.current) return;
      setProfile(data);
      setIsConflict(false);
      setError(null);
      setSaveSuccess(false);
    } catch (err) {
      if (activeClient.current !== profileClient || currentGeneration !== generation.current) return;
      setError(err.message || "No se pudo recargar el perfil.");
    } finally {
      if (activeClient.current === profileClient && currentGeneration === generation.current) setIsLoading(false);
    }
  }

  return {
    profile,
    isLoading,
    error,
    isSaving,
    saveSuccess,
    save,
    clearSuccess,
    isConflict,
    reload,
  };
}

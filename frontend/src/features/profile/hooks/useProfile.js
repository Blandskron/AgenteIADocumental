import { useState, useEffect } from "react";
import { getProfile, updateProfile } from "../api/profile.api";

export function useProfile(profileClient, onProfileUpdated) {
  const [profile, setProfile] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (!profileClient) return;

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    getProfile(profileClient)
      .then((data) => {
        if (isMounted) {
          setProfile(data);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || "No se pudo cargar el perfil.");
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [profileClient]);

  async function save(updatedData) {
    if (!profileClient) return false;

    setIsSaving(true);
    setSaveSuccess(false);
    setError(null);

    try {
      const data = await updateProfile(profileClient, updatedData);
      setProfile(data);
      setSaveSuccess(true);
      if (onProfileUpdated) {
        onProfileUpdated(data);
      }
      return true;
    } catch (err) {
      setError(err.message || "No se pudo guardar el perfil.");
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  function clearSuccess() {
    setSaveSuccess(false);
  }

  return {
    profile,
    isLoading,
    error,
    isSaving,
    saveSuccess,
    save,
    clearSuccess,
  };
}

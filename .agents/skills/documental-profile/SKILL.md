---
name: documental-profile
description: "Mantener ProfileServices al cambiar su API, persistencia o integración. Gestiona el perfil de contacto y el avatar privado de la cuenta autenticada."
---

# documental-profile

Lee las [instrucciones del ámbito](../../../backend/ProfileServices/AGENTS.md) y abre desde el [README](../../../backend/ProfileServices/README.md) la guía del contrato o de operación relevante.

1. Mantén perfil propio, GET con versión y PUT con expected_version al modificar escrituras.
2. Comprueba vigencia con profile_identity_is_current y preserva el avatar JPEG privado.
3. Prueba conflictos y refresh con el editor web, incluida la conservación de borradores.

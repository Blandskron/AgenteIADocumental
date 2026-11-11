---
name: documental-frontend
description: "Cambiar o verificar la interfaz React, accesibilidad, sesión o adaptadores HTTP del frontend documental."
---

# documental-frontend

Lee las [instrucciones del ámbito](../../../frontend/AGENTS.md) y abre desde el [README](../../../frontend/README.md) la guía del contrato o de operación relevante.

1. Mantén la generación de solicitud ligada a sesión y tenant. Una renovación de credenciales conserva el editor activo; un cambio de identidad descarta resultados anteriores.
2. Usa los tokens de superficies y texto junto con las primitivas existentes. Comprueba contraste en ambos temas, foco de teclado y la vista en anchos estrechos cuando cambie el flujo.
3. Ejecuta la secuencia de verificación de la guía de desarrollo. Compila antes de Playwright, que sirve dist en loopback con contratos HTTP sintéticos.

[Comandos de verificación](../../../frontend/docs/DEVELOPMENT.md#verificación).

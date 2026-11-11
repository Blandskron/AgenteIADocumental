---
name: documental-rag
description: "Mantener RagDocumentChatServices al cambiar su API, persistencia o integración. Recupera fragmentos autorizados y devuelve respuestas con fuentes a partir del contexto documental."
---

# documental-rag

Lee las [instrucciones del ámbito](../../../backend/RagDocumentChatServices/AGENTS.md) y abre desde el [README](../../../backend/RagDocumentChatServices/README.md) la guía del contrato o de operación relevante.

1. Rastrea preguntas, resúmenes e historial antes de tocar el filtro de recuperación.
2. Comprueba el alcance de propietario, empresa y asignaciones antes de construir el contexto para Groq.
3. Prueba permisos con PostgreSQL y usa un transporte simulado para el contrato de Groq.

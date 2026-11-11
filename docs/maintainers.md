# Documentación y skills del repositorio

Empieza por el README del ámbito que vas a cambiar. Cada uno presenta un diagrama y enlaza las guías y sus instrucciones AGENTS.md. Los detalles se mantienen en docs/ junto al código que describen. Para el sistema completo, consulta [arquitectura](architecture.md), [operación](operations.md) y [verificación](release/README.md).

Codex descubre las skills versionadas en .agents/skills. Los AGENTS.md locales enlazan la skill de su ámbito para facilitar el acceso desde el componente. [Documentación de OpenAI sobre skills de repositorio](https://developers.openai.com/blog/skills-agents-sdk)

| Ámbito | Entrada | Skill |
| --- | --- | --- |
| Proyecto | [README](../README.md) | [documental-project](../.agents/skills/documental-project/SKILL.md) |
| Backend | [README](../backend/README.md) | [documental-backend](../.agents/skills/documental-backend/SKILL.md) |
| Frontend | [README](../frontend/README.md) | [documental-frontend](../.agents/skills/documental-frontend/SKILL.md) |
| Base de datos | [README](../scripts/database/README.md) | [documental-database](../.agents/skills/documental-database/SKILL.md) |
| AuthServices | [README](../backend/AuthServices/README.md) | [documental-auth](../.agents/skills/documental-auth/SKILL.md) |
| RagDocumentEmbeddingServices | [README](../backend/RagDocumentEmbeddingServices/README.md) | [documental-ingest](../.agents/skills/documental-ingest/SKILL.md) |
| RagDocumentChatServices | [README](../backend/RagDocumentChatServices/README.md) | [documental-rag](../.agents/skills/documental-rag/SKILL.md) |
| DocumentSearchServices | [README](../backend/DocumentSearchServices/README.md) | [documental-search](../.agents/skills/documental-search/SKILL.md) |
| DocumentAccessServices | [README](../backend/DocumentAccessServices/README.md) | [documental-access](../.agents/skills/documental-access/SKILL.md) |
| DocumentLibraryServices | [README](../backend/DocumentLibraryServices/README.md) | [documental-library](../.agents/skills/documental-library/SKILL.md) |
| DocumentTransferServices | [README](../backend/DocumentTransferServices/README.md) | [documental-transfer](../.agents/skills/documental-transfer/SKILL.md) |
| ConversationServices | [README](../backend/ConversationServices/README.md) | [documental-conversations](../.agents/skills/documental-conversations/SKILL.md) |
| ProfileServices | [README](../backend/ProfileServices/README.md) | [documental-profile](../.agents/skills/documental-profile/SKILL.md) |
| DocumentExportServices | [README](../backend/DocumentExportServices/README.md) | [documental-export](../.agents/skills/documental-export/SKILL.md) |
| GoogleDriveImportServices | [README](../backend/GoogleDriveImportServices/README.md) | [documental-drive](../.agents/skills/documental-drive/SKILL.md) |

Al cambiar una API, revisa el contrato y sus consumidores. Si cambias el despliegue, actualiza la guía operativa y su diagrama. Cita el commit o la imagen probada al registrar resultados.

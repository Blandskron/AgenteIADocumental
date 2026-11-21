---
title: Arquitectura del Módulo de Custodia
tags: [arquitectura, custodia, seguridad]
aliases: [Custodia-Core]
doc_code: NOTE-S3-01
---

# Arquitectura del Módulo de Custodia

El módulo de custodia sintético delega la rotación de claves de cifrado al componente [[Politica-Rotacion-Claves]] y registra cada evento en la bitácora definida en [[Registro-Auditoria-Interna]].

El algoritmo obligatorio para secretos en reposo es Fernet con identificador de llave versionado (`secrets1.`). #seguridad #cifrado

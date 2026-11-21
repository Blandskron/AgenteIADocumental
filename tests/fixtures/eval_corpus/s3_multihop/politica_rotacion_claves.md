---
title: Política de Rotación de Claves
tags: [seguridad, claves, rotacion]
aliases: [Politica-Rotacion-Claves]
doc_code: NOTE-S3-02
---

# Política de Rotación de Claves

Toda llave de cifrado debe rotarse cada **90 días** conservando las llaves previas en `SECRETS_PREVIOUS_KEYS` durante una ventana de transición de 14 días.

Cuando se ejecuta una rotación, el operador debe verificar el procedimiento de contingencia descrito en [[Procedimiento-Revocacion-Emergencia]]. #operaciones

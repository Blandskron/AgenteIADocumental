# Corpus Sintético de Evaluación (`S1`–`S5`)

Corpus **100 % sintético** y libre de datos personales o credenciales para medir la evolución del núcleo RAG (Fases 2–3) y de Knowledge Studio (Fase 4).

## Conjuntos incluidos

| Set | Directorio | Propósito |
| --- | --- | --- |
| `S1-single` | `s1_single/` | Acta de reunión sintética con decisiones, responsables, fechas y glosario para evaluar resúmenes, minutas, FAQ y chunking estructural. |
| `S2-multi` | `s2_multi/` | Informes trimestrales ficticios (`Q1`–`Q4` de dos años) con métricas numéricas y discrepancias deliberadas para evaluar recuperación exacta, tablas de evidencia y detección de contradicciones/lagunas. |
| `S3-multihop` | `s3_multihop/` | Notas Markdown estilo bóveda (`frontmatter` YAML + `[[wikilinks]]` + `#tags`) donde las respuestas requieren encadenar 3 documentos. |
| `S4-adversarial` | `s4_adversarial/` | Casos de seguridad y robustez: prompt-injection documental, HTML/SVG malicioso, patrones de path traversal (`../`), Unicode RTL (`\u202e`), prompt-splitting y generador determinista de zip-bomb sintética en memoria. |
| `S5-noise` | `s5_noise/` | OCR ruidoso, tablas rotas, listas vacías y documentos sin métricas para validar degradación honesta (`gaps[]` / sin alucinación). |

## Ground truth y ejecución

El archivo [`ground_truth.json`](ground_truth.json) define las consultas, documentos esperados, términos/valores exactos y expectativas adversariales.

Ejecuta el harness reproducible desde la raíz:

```bash
python3 scripts/eval/run_eval_baseline.py
```

El script valida el corpus, calcula métricas reproducibles de línea base (cobertura léxica, recuperación por subcadena estilo `ILIKE`, chunking por ventana fija y controles adversariales) y escribe el reporte JSON en `.release-reports/EVAL_BASELINE.json`.


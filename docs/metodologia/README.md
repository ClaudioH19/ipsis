# Fichas metodológicas

Cada técnica de la librería se documenta en una ficha antes de considerarse
estable. La ficha acompaña al código y se actualiza cuando cambia su
algoritmo.

## Plantilla obligatoria

1. Propósito.
2. Alcance y no-alcance.
3. Entradas y salidas versionadas.
4. Algoritmo y desempates.
5. Supuestos.
6. Invariantes.
7. Parámetros y defaults.
8. Complejidad y recursos.
9. Fallos y fallback.
10. Seguridad y privacidad.
11. Pruebas técnicas.
12. Limitaciones.
13. Referencias y procedencia.
14. Estado: experimental, estable, deprecado o pendiente de calibración.

Los valores aún no contrastados contra un golden set se identifican como
`pendiente de calibración`; nunca como una garantía de precisión.

## Fichas, en el orden de una consulta

1. [Recuperación híbrida](recuperacion.md): e5 + BM25 en Qdrant con RRF.
2. [Capa léxica](lexico.md): `terminos()`, BM25, TF-IDF y las señales
   `s_oov`, foco, `s_foco`, `s_cov` y `s_lex`.
3. [Reranker](reranker.md): cross-encoder en medium y heavy.
4. [Lector QA](lector.md): tramo literal o «sin respuesta», señal `s_qa`.
5. [Política `cascada_v1`](politica.md): `ok`, `relacionado` o
   `sin_respuesta`.
6. [Calibración](calibracion.md): umbrales con riesgo ≤ α
   (Clopper-Pearson).
7. [Multilenguaje](multilenguaje.md): paquetes de idioma y tonos.
8. [Banco de evaluación](evaluacion.md): formato, categorías y splits.

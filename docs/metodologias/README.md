# Fichas metodológicas

Cada técnica de la librería debe documentarse antes de considerarse estable.
La ficha acompaña al código y debe actualizarse cuando cambie su algoritmo.

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

Los valores aún no contrastados contra un golden set deben identificarse como
`pendiente de calibración`; nunca como una garantía de precisión.

Fichas actuales:

- [Recuperación híbrida Qdrant](recuperacion.md).
- [Banco de evaluación](evaluacion.md).

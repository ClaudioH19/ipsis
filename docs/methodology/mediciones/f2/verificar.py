"""Comprueba los criterios y los bytes de ambos árboles archivados."""
from pathlib import Path
import hashlib
import json
import zipfile

carpeta = Path(__file__).resolve().parent
metadata = json.loads((carpeta / "metadata.json").read_text(encoding="utf-8"))
validacion = json.loads((carpeta / "validacion.json").read_text(encoding="utf-8"))
assert all(validacion["criterios"].values()), validacion["criterios"]
for archivo, clave in (("baseline-code.zip", "before_code"), ("final-code.zip", "final_code")):
    with zipfile.ZipFile(carpeta / archivo) as z:
        h = hashlib.sha256()
        for nombre in sorted(z.namelist(), key=Path):
            h.update(nombre.encode())
            h.update(b"\0")
            h.update(z.read(nombre))
        assert "sha256:" + h.hexdigest() == metadata[clave], archivo
        print(archivo, len(z.namelist()), "archivos; huella exacta")
print("G1–G6:", validacion["criterios"])

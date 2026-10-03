# Wordmark fonts (build input only)

Used by `../build.py` to set the logo grid's wordmarks in Blender; the browser
never downloads them (the wordmarks are exported as meshes in `stop.glb`).

All are from Google Fonts and licensed under the SIL Open Font License 1.1
(https://openfontlicense.org): Outfit, Space Grotesk, Syne, DM Serif Display,
Nunito, Archivo, Instrument Serif, Inter Tight, Fraunces, Pacifico.
Static instances at the weights the landing page uses, with overlapping
outlines removed (fontTools `removeOverlaps`) so Blender fills them cleanly.

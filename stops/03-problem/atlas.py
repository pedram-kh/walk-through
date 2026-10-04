"""Stop 03 card faces: one texture (cards.jpg) holding every card of the three rows.

Each card is drawn like the landing HTML's CreativeCard (248 x 183 px): the photo
(cover-cropped), a 1 px border at 8% white and the label chip (mono 10 px, 72% white
on 55% black, 6 px from the bottom-left corner). Photos are the catalyst-growth.com
set already downloaded for stop 01 (stops/01-hero/media/images), one per card.
Run with the system Python (needs Pillow), before build.py:
  python3 stops/03-problem/atlas.py
Outputs beside this file: cards.jpg, cards.json (cells, labels, photos)
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
MEDIA = OUT.parent / '01-hero' / 'media'
ROWS, LOOP = 3, 6                 # 6 cards per row: 5 on screen, 1 waiting off the row's end
CARD = (248, 183)                 # landing card size in px
SCALE = 2                         # texture pixels per landing px
PAD = 8                           # texture pixels around each card, so mipmaps do not bleed
LABELS = ['UGC', 'HI-FI', 'MOTION', 'CREATOR', 'STATIC', 'STILL']   # landing p2Lab
ROW_SEED = [0, 2, 4]              # landing p2Card seeds: label = LABELS[(seed + j * 5) % 6]
FONT = '/System/Library/Fonts/Menlo.ttc'   # stands in for Geist Mono at 10 px


def photos():
    """One file per distinct photo, in media.json order."""
    media = json.loads((MEDIA / 'media.json').read_text())
    seen, files = set(), []
    for item in media['images']:
        if item['source_url'] not in seen:
            seen.add(item['source_url'])
            files.append(item['file'])
    return files


def cover(image, size):
    w, h = size
    scale = max(w / image.width, h / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left, top = (image.width - w) // 2, (image.height - h) // 2
    return image.crop((left, top, left + w, top + h))


def card_face(photo, label):
    w, h = CARD[0] * SCALE, CARD[1] * SCALE
    face = cover(Image.open(MEDIA / photo).convert('RGB'), (w, h)).convert('RGBA')
    over = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(over)
    draw.rectangle((0, 0, w - 1, h - 1), outline=(255, 255, 255, round(0.08 * 255)), width=SCALE)
    font = ImageFont.truetype(FONT, 10 * SCALE)
    spaced = label                                   # 0.08em tracking, drawn letter by letter
    advance = [draw.textlength(c, font=font) + 0.8 * SCALE for c in spaced]
    text_w, text_h = sum(advance) - 0.8 * SCALE, 10 * SCALE
    pad_x, pad_y = 5 * SCALE, 4 * SCALE
    x0, y1 = 6 * SCALE, h - 6 * SCALE
    draw.rectangle((x0, y1 - text_h - 2 * pad_y, x0 + text_w + 2 * pad_x, y1), fill=(0, 0, 0, round(0.55 * 255)))
    x = x0 + pad_x
    for c, a in zip(spaced, advance):
        draw.text((x, y1 - pad_y - text_h * 0.9), c, font=font, fill=(255, 255, 255, round(0.72 * 255)))
        x += a
    return Image.alpha_composite(face, over).convert('RGB')


files = photos()
assert len(files) >= ROWS * LOOP, f'need {ROWS * LOOP} photos, found {len(files)}'
# About half the set is black and white; interleave so every row mixes colour and mono.
ORDER = [0, 8, 1, 9, 2, 10,   11, 3, 12, 4, 13, 5,   6, 14, 7, 15, 16, 17]
files = [files[i] for i in ORDER]
cell_w, cell_h = CARD[0] * SCALE + 2 * PAD, CARD[1] * SCALE + 2 * PAD
atlas = Image.new('RGB', (cell_w * LOOP, cell_h * ROWS), (7, 7, 10))
cells = []
for row in range(ROWS):
    for k in range(LOOP):
        n = row * LOOP + k
        label = LABELS[(ROW_SEED[row] + k * 5) % 6]
        face = card_face(files[n], label)
        x, y = k * cell_w, row * cell_h
        # repeat the face's edge pixels into the padding (no dark seams when mipmapped)
        atlas.paste(face.resize((cell_w, cell_h)), (x, y))
        atlas.paste(face, (x + PAD, y + PAD))
        cells.append({'row': row, 'index': k, 'label': label, 'photo': files[n],
                      'uv': [round((x + PAD) / atlas.width, 5), round(1 - (y + PAD + face.height) / atlas.height, 5),
                             round(face.width / atlas.width, 5), round(face.height / atlas.height, 5)]})
atlas.save(OUT / 'cards.jpg', quality=84, optimize=True, progressive=True)
(OUT / 'cards.json').write_text(json.dumps({'file': 'cards.jpg', 'size': list(atlas.size), 'cells': cells}, indent=1))
print(f'ATLAS {atlas.size[0]}x{atlas.size[1]} cards={len(cells)} {(OUT / "cards.jpg").stat().st_size // 1024} KB')

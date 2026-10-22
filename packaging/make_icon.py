#!/usr/bin/env python3
"""Draw the editor's own icon (no game assets): packaging/icon.png (256x256)."""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
S = 256
BG, EDGE, ACCENT, CREAM = (24, 29, 26, 255), (58, 68, 61, 255), (240, 160, 50, 255), (232, 226, 208, 255)


def main():
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, S - 8, S - 8), radius=40, fill=BG, outline=EDGE, width=6)
    # floppy-disk "save" body
    d.rounded_rectangle((52, 44, 204, 212), radius=14, fill=ACCENT)
    d.rectangle((84, 44, 172, 100), fill=BG)              # shutter
    d.rectangle((140, 54, 160, 92), fill=ACCENT)          # shutter window
    d.rounded_rectangle((72, 128, 184, 196), radius=8, fill=CREAM)   # label
    # a tiny car on the label
    d.rounded_rectangle((90, 152, 166, 176), radius=6, fill=BG)
    d.polygon([(104, 152), (114, 138), (144, 138), (154, 152)], fill=BG)
    d.ellipse((98, 168, 114, 184), fill=ACCENT, outline=BG, width=3)
    d.ellipse((142, 168, 158, 184), fill=ACCENT, outline=BG, width=3)
    img.save(os.path.join(HERE, 'icon.png'))
    print('written', os.path.join(HERE, 'icon.png'))


if __name__ == '__main__':
    main()

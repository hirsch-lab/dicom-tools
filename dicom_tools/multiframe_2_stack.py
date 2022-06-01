from PIL import Image, ImageSequence
from pathlib import Path
import os

# Checking paths before using

os.chdir(os.path.join(os.getcwd(), "tests_part2"))

path_multiframe = os.path.join(os.getcwd(), "tiff_multiframe")
inp_path = Path(path_multiframe)


for i in os.listdir(inp_path):
    if i == ".DS_Store":
        os.remove(os.path.join(inp_path, i))
    elif i.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff')):
        img = Image.open(os.path.join(inp_path, i))
        if img.n_frames > 1:
            for idx, page in enumerate(ImageSequence.Iterator(img)):
                page.save(os.path.join(inp_path, i.rsplit('.', 1)[0] + '_slice%d.tif' %idx))
            try:
                Path(os.path.join(inp_path, i)).unlink()
            except OSError as e:
                print('Error: %s : %s' % (i, e.strerror))




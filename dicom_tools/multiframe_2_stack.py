import cv2 as cv
import matplotlib.pyplot as plt
from PIL import Image, ImageSequence
import os

os.chdir(os.path.join(os.getcwd(), "tests_part2"))
print(os.getcwd())

path_multiframe = os.path.join(os.getcwd(), "tiff_multiframe")
path_tiff_stack = os.path.join(os.getcwd(), "tiff_stack")
try:
    os.makedirs(path_tiff_stack)
except:
    print('already exists')

img = Image.open(os.path.join(path_multiframe, os.listdir(path_multiframe)[0]))
for i, page in enumerate(ImageSequence.Iterator(img)):
    page.save(os.path.join(path_tiff_stack, "slice%d.tif" % i))


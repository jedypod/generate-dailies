import OpenImageIO as oiio
from OpenImageIO import ImageInput, ImageOutput
from OpenImageIO import ImageBuf, ImageSpec, ImageBufAlgo
import numpy

import os, sys
import shlex, subprocess
import glob


OCIO_CONFIG = os.getenv("OCIO")
if not OCIO_CONFIG:
	OCIO_CONFIG = "/mnt/cave/dev/ocio/aces/config.ocio"

RESIZE_WIDTH = 2048



def run_command(args, wait=False):
    try:
        if (wait):
            p = subprocess.Popen(
                args, 
                stdout = subprocess.PIPE)
            p.wait()
        else:
            p = subprocess.Popen(
                args, 
                stdin = None, stdout = None, stderr = None, close_fds = True)

        (result, error) = p.communicate()
        
    except subprocess.CalledProcessError as e:
        sys.stderr.write(
            "common::run_command() : [ERROR]: output = %s, error code = %s\n" 
            % (e.output, e.returncode))
    return result 



imgpath = '/mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/monkey_test/M07-2031.00190.exr'
# imgpath = '/mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/smaller_grid.exr'

# Output file path
# img_output_path = os.path.join(os.getcwd(), os.path.splitext(imgpath)[0] + ".tif")

# srcbuf = ImageBuf(imgpath)
# print type(srcbuf)
imgin = ImageInput.open(imgpath)
print type(imgin)

srcbuf = ImageBuf(imgin, imgin.spec())
print type(srcbuf) 

print srcbuf.nsubimages

# dstspec = ImageSpec(RESIZE_WIDTH, 1152, 3, oiio.UINT16)
# dstbuf = ImageBuf(dstspec)
# exp = 0.5
# ImageBufAlgo.mul(srcbuf, srcbuf, (exp, exp, exp, 1.0))

# Apply OCIO Display
ImageBufAlgo.ociodisplay(srcbuf, srcbuf, "ACES", "RRT", colorconfig=OCIO_CONFIG)
# print dstbuf.spec().format
# Setup Output Format
# imgspec.set_format(oiio.TypeDesc("uint16"))
# srcbuf.set_write_format("uint16")
# srcbuf.specmod().attribute("compression", "lzw")
# print srcbuf.file_format_name

# Resize
halfres_roi = oiio.ROI(0, RESIZE_WIDTH, 0, RESIZE_WIDTH)
ImageBufAlgo.fit(srcbuf, srcbuf, "lanczos3", 6.0, roi=halfres_roi)

# Remove alpha channel
ImageBufAlgo.channels(srcbuf, srcbuf, (0,1,2))
srcbuf.get_pixels(oiio.UINT16).tofile(sys.stdout)

# px = pixels.tofile(sys.stdout)
# print type(px)
# print px
# print type(px)

# sys.stdout.write(px)

# Write Output Image

# srcbuf.write(img_output_path)

# imgoutput = ImageOutput.create(img_output_path)
# if not imgoutput:
# 	print "Error:", oiio.geterror()

# imgspec = srcbuf.spec()
# test = imgoutput.open(img_output_path, imgspec)
# sys.stdout.write(str(test))

# imgoutput.write_image(srcbuf.get_pixels())
# imgoutput.close()


# ffmpeg-10bit -f rawvideo -pixel_format rgb48le -video_size 1920x1080 -framerate 24 -i test.raw -c:v libx264 -profile:v high444 -preset veryslow -g 1 -tune film -crf 13 -pix_fmt yuv444p10le -vf "colormatrix=bt601:bt709" test.mov
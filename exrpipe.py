import OpenImageIO as oiio
from OpenImageIO import ImageInput, ImageOutput
from OpenImageIO import ImageBuf, ImageSpec, ImageBufAlgo


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

imgpath = '/mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/airplane_night_test/exr/M08-0525/M08-0525_001000.exr'

# Output file path
img_output_path = os.path.join(os.getcwd(), os.path.splitext(imgpath)[0] + ".tif")

imgbuf = ImageBuf(imgpath)

# Apply OCIO Display
imgbuf = ImageBufAlgo.ociodisplay(imgbuf, "ACES", "RRT", colorconfig=OCIO_CONFIG)

# Setup Output Format
# imgspec.set_format(oiio.TypeDesc("uint16"))
imgbuf.set_write_format("uint16")
imgbuf.specmod().attribute("compression", "lzw")
print imgbuf.file_format_name

# Resize
halfres_roi = oiio.ROI(0, RESIZE_WIDTH, 0, RESIZE_WIDTH)
imgbuf = ImageBufAlgo.fit(imgbuf, "lanczos3", 6.0, roi=halfres_roi)

# Remove alpha channel
ImageBufAlgo.channels(imgbuf, imgbuf, (0,1,2, 1.0))


# Write Output Image

# imgbuf.write(img_output_path)

imgoutput = ImageOutput.create(img_output_path)
if not imgoutput:
	print "Error:", oiio.geterror()

imgspec = imgbuf.spec()
test = imgoutput.open(img_output_path, imgspec)
sys.stdout.write(str(test))

imgoutput.write_image(imgbuf.get_pixels())
imgoutput.close()
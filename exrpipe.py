import OpenImageIO as oiio
from OpenImageIO import ImageInput, ImageOutput
from OpenImageIO import ImageBuf, ImageSpec, ImageBufAlgo

import os

OCIO_CONFIG = os.getenv("OCIO")
if not OCIO_CONFIG:
	OCIO_CONFIG = "/mnt/cave/dev/ocio/aces/config.ocio"


# def transcode(imgpath=None):
imgpath = '/mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/monkey_test/M07-2031_000188.exr'

buf_src = ImageBuf(imgpath)
if buf_src == None:
	print "Error:", oiio.geterror()
	return

# Gather information about source image
spec_src = buf_src.spec()
input_width = spec_src.width
# input_width = 3072
input_height = spec_src.height
# input_height = 1320
input_ar = float(input_width)/float(input_height)
input_datatype = spec_src.format
input_channels = spec_src.nchannels
print "Input image is {0}x{1} par {2} type {3} channels {4}".format(input_width, input_height, input_ar, input_datatype, input_channels)

for i in range(len(spec_src.extra_attribs)):
	print i, spec_src.extra_attribs[i].name, str(spec_src.extra_attribs[i].type), " :"
	print "\t", spec_src.extra_attribs[i].value

print spec_src.channel_name(1)

	# RWIDTH = 1920

	# buf_display = ImageBuf(ImageSpec(input_width, input_height, 3, oiio.HALF))

	# # OCIO Color Conversions
	# # ImageBufAlgo.colorconvert(buf_resize, buf_resize, "lin_ap0", "lin_ap1", colorconfig=OCIO_CONFIG)
	# ImageBufAlgo.ociodisplay(buf_display, buf_src, "ACES", "RRT", colorconfig=OCIO_CONFIG)

	# # Make a new image buffer for the output resized image
	# buf_resize = ImageBuf()
	
	# # # Make a new image buffer for the range compressed log image
	# # buf_compress = ImageBuf()
	# # ImageBufAlgo.rangecompress(buf_compress, buf_src)

	# ImageBufAlgo.resize(buf_resize, buf_display, "lanczos3", 6.0, 
	# 			oiio.ROI(0, RWIDTH, 0, int(RWIDTH/input_ar), 0, 1, 0, buf_display.nchannels))
	# # # ImageBufAlgo.rangeexpand(buf_resize, buf_resize)

	# outpath = '/mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/output/test.tif'
	# out_type = "tif"
	# output = ImageOutput.create(outpath)
	# if not output :
	# 	print "Error:", oiio.geterror()

	# out_spec = ImageSpec(buf_src.spec().width, buf_src.spec().height, 3, oiio.UINT16)

	# ok = output.open(outpath, out_spec, oiio.Create)
	# if not ok:
	# 	print "Could not open", outpath, ":", output.geterror()

	# # buf_resize.write(outpath)





# if __name__=="__main__":
# 	# imgpath = '/mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/test/exr/M26-1917_%06d.exr'
# 	# imgpath = '/mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/test/exr/M26-1917_000050.exr'
# 	imgpath = '/mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/monkey_test/M07-2031_000188.exr'
# 	transcode(imgpath)


'''

http://lists.openimageio.org/pipermail/oiio-dev-openimageio.org/2016-March/000384.html
https://github.com/OpenImageIO/oiio/issues/1764
http://lists.openimageio.org/pipermail/oiio-dev-openimageio.org/2013-October/006298.html
https://gist.github.com/justinfx/33931727822fbebc4aa5

--autotrim = autocrop
http://lists.openimageio.org/pipermail/oiio-dev-openimageio.org/2013-July/012696.html


# 1. Read the original image
Src = ImageBuf ("tahoeHDR.exr")
# 2. Range compress to a logarithmic scale
Compressed = ImageBuf ()
ImageBufAlgo.rangecompress (Compressed, Src)
# 3. Now do the resize
Dst = ImageBuf ()
roi = ROI (0, 640, 0, 480, 0, 1, 0, Compressed.nchannels)
ImageBufAlgo.resize (Dst, Compressed, "lanczos3", 6.0, roi)
# 4. Expand range to be linear again (operate in-place)
ImageBufAlgo.rangeexpand (Dst, Dst)



# https://gist.github.com/Brainiarc7/ebf3091efd2bf0a0ded0f9715cd43a38
# https://acescentral.com/t/using-aces-shaper-spaces-in-ocio-bakelut/589/2

# -vf colormatrix=bt601:bt709
# http://www.studiosysadmins.com/board/threadview/5320/
# https://ffmpeg.org/ffmpeg-protocols.html#pipe
# https://stackoverflow.com/questions/34167691/pipe-opencv-images-to-ffmpeg-using-python#




oiiotool hdr.exr --rangecompress --resize 512x512 --rangeexpand -o resized.exr


oiiotool -v -i /mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/M26-1917.MLV/M26-1917_%06d.exr --frames 50-149 -colorconvert lin_ap0 lin_ap1 --ociodisplay ACES RRT --resize 1920x0 --compression lzw


buf = oiio.ImageBuf(imgpath)
cropped = oiio.ImageBuf()
extended = oiio.ImageBuf(oiio.ImageSpec (3693, 2077, 3, oiio.FLOAT))
resized = oiio.ImageBuf(oiio.ImageSpec (1920, 1080, 3, oiio.FLOAT))
oiio.ImageBufAlgo.crop(cropped, buf, oiio.ROI(108, 3801, 514, 2085), nthreads=4)
oiio.ImageBufAlgo.paste(extended, 0, 253, 0, 0, cropped, nthreads=4)
oiio.ImageBufAlgo.resize(resized, extended, nthreads=4)
oiio.ImageBufAlgo.render_text(resized, 1300, 1030, "00001.cr2", 50, "Arial")
oiio.ImageBufAlgo.render_text(resized, 1600, 1030, "00:00:00", 50, "Arial")
buf.write("image.tiff")
resized.write("imageresized.jpg")


'''




'''
	imgpath = '/mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/test/exr/M26-1917_%06d.exr'

	image_input = ImageInput.open(imgpath)

	if image_input == None :
		print "Error:", oiio.geterror()
		return
	
	pixels = image_input.read_image(oiio.FLOAT)
	image_input.close()


	print image_input.format_name()
	spec = image_input.spec()
	print "resolution ", spec.width, "x", spec.height


	image_output = ImageOutput.create("tif")
	if not image_output:
		print "Error:", oiio.geterror()

	if image_output:
		print image_output.format_name(), "supports..."
		print "tiles?", image_output.supports("tiles")
		print "multi-image?", image_output.supports("multiimage")
		print "MIP maps?", image_output.supports("mipmap")
		print "per-channel formats?", image_output.supports("channelformats")

	out_imgpath = '/mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/test/'
	out_spec = ImageSpec(1920, 1080, 3, oiio.UINT16)
	dest_buf = ImageBuf(out_spec)
	ImageBufalgo.resize(dest_buf, image_input)
	ok = image_output.open(out_imgpath, out_spec, oiio.Create)
	
	if not ok :
		print "Could not open", out_imgpath, ":", image_output.geterror()

	image_output.write_image(ok)
	image_output.close()
'''
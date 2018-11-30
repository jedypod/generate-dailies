#!/usr/bin/env python

import OpenImageIO as oiio
import numpy as np
import os, sys, argparse
from glob import glob



"""
	Commandline python program to take an openexr image sequence, apply an ocio display transform, resize, 
	and output to sdtout as raw uint16 byte data.
	Inputs:
		image sequence in /path/to/imagename.%05d.exr format
		optional: framerange to use starframe-endframe
		ocio display and ocio view to apply.
		ocio config to use
		resize width
		resize pad to fit (optional)
	Example ffmpeg command:
	./exrpipe -i '/mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/monkey_test/M07-2031.%05d.exr' -s 190 -e 200 -d ACES -v RRT -r 2048x1152| ffmpeg-10bit -f rawvideo -pixel_format rgb48le -video_size 1920x1080 -framerate 24 -i pipe:0 -c:v libx264 -profile:v high444 -preset veryslow -g 1 -tune film -crf 13 -pix_fmt yuv444p10le -vf "colormatrix=bt601:bt709" test.mov

""" 


def process_frame(frame, args):
	# Process each frame and output to stdout
	buf = oiio.ImageBuf(frame)
	spec = buf.spec()
	# Remove alpha channel
	oiio.ImageBufAlgo.channels(buf, buf, (0,1,2))

	# Apply OCIO Display
	ociodisplay = args.ociodisplay
	ocioview = args.ocioview
	if not ociodisplay:
		ociodisplay = "ACES"
	if not ocioview:
		ocioview = "RRT"

	ocioconfig = args.ocioconfig
	if not ocioconfig:
		# Try to get ocio config from $OCIO env-var
		ocioconfig = os.getenv("OCIO")
	if ociodisplay and ocioview and ocioconfig: 
		# Apply OCIO display transform onto specified image buffer
		oiio.ImageBufAlgo.ociodisplay(buf, buf, ociodisplay, ocioview, colorconfig=ocioconfig)

	# Apply Resize / Fit
	resize = args.resize
	iwidth = spec.width
	iheight = spec.height
	iar = iwidth / iheight
	if resize:
		if not "x" in resize:
			print "Error: resize must be width x height"
			return
		rwidth, rheight = resize.split('x')
		rwidth = int(rwidth)
		rheight = int(rheight)
		if rheight == 0:
			# Resize keeping aspect ratio, long side = width - calc height
			rheight = rwidth / iar

		roi = oiio.ROI(0, rwidth, 0, rheight)
		oar = rwidth / rheight
		if oar != iar:
			print "specified aspect ratio does not match input aspect ratio:\niar:{0} oar: {1}".format(iar, oar)
			oiio.ImageBufAlgo.fit(buf, buf, "lanczos3", 6.0, roi=roi)
		else:
			# Resize without fitting
			oiio.ImageBufAlgo.resize(buf, buf, "lanczos3", 6.0, roi=roi)
	buf.get_pixels(oiio.UINT16).tofile(sys.stdout)
		


def get_frames(args):
	# Get input image sequence and ensure it is existing and set up correctly.
	image_sequence = args.image_sequence
	print "Got ", image_sequence

	imgseq, imgseq_ext = os.path.splitext(image_sequence)
	# print imgseq, imgseq_ext

	if "%" in image_sequence:
		imgseq_base = image_sequence.split('%')[0]

	if "#" in image_sequence:
		imgseq_base = image_sequence.split('#')[0]
	# print imgseq_base

	frames = glob(imgseq_base + "*")
	frames.sort()
	for frame in frames:
		print frame
	return frames

		
def init():
	# Parse input arguments
	parser = argparse.ArgumentParser(
		description='Process given exr image sequence with ocio display, resize and output to stdout.')
	parser.add_argument("-i", "--image_sequence",
	                    help="Input exr image sequence. \
	                    Can be a folder containing images, a path to the first image, a %05d path, or a ##### path.")
	parser.add_argument('-s', "--start_frame", help="Start frame.")
	parser.add_argument('-e', "--end_frame", help="End frame.")
	parser.add_argument("-c", "--ocioconfig", help="Path to config.ocio to use. Optional. If not provided, $OCIO will be used.")
	parser.add_argument("-d", "--ociodisplay", help="Name of OCIO Display to use")
	parser.add_argument("-v", "--ocioview", help="Name of OCIO View to use")
	parser.add_argument("-r", "--resize", 
		help="Resize image. Can be 1920x0 to resize long edge maintaining aspect ratio. \
		Can be 1920x1080 to resize fitting width and height into box without stretching.")
	args = parser.parse_args()

	# for arg in vars(args):
		# print arg, getattr(args, arg)
	frames = get_frames(args)
	if not frames:
		print "Error: No frames found..."
		return

	for frame in frames:
		process_frame(frame, args)






if __name__=="__main__":
	init()
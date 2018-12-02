#!/usr/bin/env python
from __future__ import with_statement
import os, sys, yaml
import OpenImageIO as oiio
import numpy as np
import os, sys, re, argparse, shlex
from glob import glob
import logging

from subprocess import Popen, PIPE
from threading import Thread

"""
	Daily
	---------------------
	This is a program to render a dailies movie from an input image sequence (jpegs or exrs).
	It reads from a configuration file to define things like resize, color transforms, padding, 
	text overalys, slate frames and so forth.

"""
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
	Example Command:
	./exrpipe -i '/mnt/cave/dev/__pipeline-tools/generate_dailies/test_footage/monkey_test/M07-2031.%05d.exr' -s 190 -e 200 -d ACES -v RRT -r 2048x1152 | ffmpeg-10bit -f rawvideo -pixel_format rgb48le -video_size 1920x1080 -framerate 24 -i pipe:0 
	-c:v libx264 -profile:v high444 -preset veryslow -g 1 -tune film -crf 13 -pix_fmt yuv444p10le -vf "colormatrix=bt601:bt709" test.mov
"""

# Set up logging
os.remove('daily.log')
logger = logging.getLogger(__name__)
handler = logging.FileHandler('daily.log')
# log_format = '%(levelname)s \t%(asctime)s \t%(message)s'
log_format = '%(levelname)s \t%(message)s'
formatter = logging.Formatter(log_format)
handler.setFormatter(formatter)
logger.addHandler(handler)




def oiio_reformat(buf, owidth, oheight):
	# Reformat an incoming image buffer to the specified width and height: no resize no resampling, just changing the res
	bgbuf = oiio.ImageBuf(oiio.ImageSpec(owidth, oheight, 4, oiio.UINT16))
	oiio.ImageBufAlgo.zero(bgbuf)
	oiio.ImageBufAlgo.channels(buf, buf, (0,1,2, 1.0))
	buf = oiio.ImageBufAlgo.over(buf, bgbuf)
	oiio.ImageBufAlgo.channels(buf, buf, (0,1,2))
	return buf

def oiio_transform(buf, xoffset, yoffset):
	# transform an image without filtering
	orig_roi = buf.roi
	buf.specmod().x += xoffset
	buf.specmod().y += yoffset
	buf_trans = oiio.ImageBuf()
	oiio.ImageBufAlgo.crop(buf_trans, buf, orig_roi)
	return buf_trans


def process_frame(frame, globals_config, codec_config):
	"""
		Apply all color and reformat operations to input image, then write the frame to stdout
	"""
	logger.info("Processing frame: \t{0}".format(os.path.split(frame)[-1]))
	# Setup image buffer
	buf = oiio.ImageBuf(frame)
	spec = buf.spec()
	
	# Get Codec Config and gather information
	iwidth = spec.width
	iheight = spec.height
	iar = float(iwidth) / float(iheight)

	px_filter = globals_config['filter']
	owidth = globals_config['width']
	oheight = globals_config['height']
	fit = globals_config['fit']
	cropwidth = globals_config['cropwidth']
	cropheight = globals_config['cropheight']

	# Remove alpha channel
	oiio.ImageBufAlgo.channels(buf, buf, (0,1,2))

	# Apply OCIO Display
	ocioconfig = globals_config['ocioconfig']
	ociocolorconvert = globals_config['ociocolorconvert']
	ociolook = globals_config['ociolook']
	ociodisplay = globals_config['ociodisplay']
	ocioview = globals_config['ocioview']
	if ocioconfig:
		if ociocolorconvert:
			oiio.ImageBufAlgo.ociocolorconvert(buf, buf, ociocolorconvert, ocioview, colorconfig=ocioconfig)
		if ociolook:
			oiio.ImageBufAlgo.ociolook(buf, buf, ociolook, ocioview, colorconfig=ocioconfig)
		if ociodisplay and ocioview: 
			# Apply OCIO display transform onto specified image buffer
			oiio.ImageBufAlgo.ociodisplay(buf, buf, ociodisplay, ocioview, colorconfig=ocioconfig)


	# Setup for width and height
	if not owidth:
		resize = False
	else:
		resize = True
		# If no output height specified, resize keeping aspect ratio, long side = width - calc height
		oheight_noar = int(owidth / iar)
		if not oheight:
			oheight = oheight_noar
		oar = float(owidth) / float(oheight)


	# Apply cropwidth / cropheight to remove pixels on edges before applying resize
	if cropwidth or cropheight:
		# Handle percentages
		if "%" in cropwidth:
			cropwidth = int(float(cropwidth.split('%')[0])/100*iwidth)
			logger.info("Got crop percentage: {0}".format(cropwidth))
		if "%" in cropheight:
			cropheight = int(float(cropheight.split('%')[0])/100*iheight)
			logger.info("Got crop percentage: {0}".format(cropheight))

		buf = oiio.ImageBufAlgo.crop(buf, roi=oiio.ROI(cropwidth / 2, iwidth - cropwidth / 2, cropheight / 2, iheight - cropheight / 2))
		# buf.set_full(cropwidth / 2, iwidth - cropwidth / 2, cropheight / 2, iheight - cropheight / 2, 0, 0)

		logger.debug("CROPPED:{0} {1}".format(buf.spec().width, buf.spec().height))

		# Recalculate input resolution and aspect ratio - since it may have changed with crop
		iwidth = iwidth - cropwidth / 2
		iheight = iheight - cropheight / 2
		iar = float(iwidth) / float(iheight)

	# Apply Resize / Fit
	# If input and output resolution are the same, do nothing
	# If output width is bigger or smaller than input width, first resize without changing input aspect ratio
	# If "fit" is true, 
	# If output height is different than input height: transform by the output height - input height / 2 to center, 
	# then crop to change the roi to the output res (crop moves upper left corner)

	identical = owidth == iwidth and oheight == iheight
	resize = not identical and resize
	if resize:
		logger.info("Performing Resize: \n\tinput: {0}x{1} ar{2}\n\toutput: {3}x{4} ar{5}".format(iwidth, iheight, iar, owidth, oheight, oar))

		if iwidth != owidth:
			# Perform resize, no change in AR
			logger.debug("{0}, {1}".format(oheight_noar, px_filter))
			if px_filter:
				# (bug): using "lanczos3", 6.0, and upscaling causes artifacts
				# (bug): dst buf must be assigned or ImageBufAlgo.resize doesn't work
				buf = oiio.ImageBufAlgo.resize(buf, px_filter, roi=oiio.ROI(0, owidth, 0, oheight_noar))
			else:
				buf = oiio.ImageBufAlgo.resize(buf, roi=oiio.ROI(0, owidth, 0, oheight_noar))
				
		if fit:
			# # If fitting is enabled..
			height_diff = oheight - oheight_noar
			logger.debug("Height difference: {0} {1} {2}".format(height_diff, oheight, oheight_noar))

			# If we are cropping to a smaller height we need to transform first then crop
			# If we pad to a taller height, we need to crop first, then transform.
			if oheight < oheight_noar:
				# If we are cropping...
				buf = oiio_transform(buf, 0, height_diff/2)
				buf = oiio.ImageBufAlgo.crop(buf, roi=oiio.ROI(0, owidth, 0, oheight))
			elif oheight > oheight_noar:
				# If we are padding...
				buf = oiio.ImageBufAlgo.crop(buf, roi=oiio.ROI(0, owidth, 0, oheight))
				buf = oiio_transform(buf, 0, height_diff/2)
			
	# Apply Cropmask if enabled
	enable_cropmask = globals_config['cropmask']
	if enable_cropmask:
		cropmask_ar = globals_config['cropmask_ar']
		cropmask_opacity = globals_config['cropmask_opacity']
		if not cropmask_ar or not cropmask_opacity:
			loggger.error("Cropmask enabled, but no crop specified. Skipping cropmask...")
		else:
			cropmask_height = int(round(owidth / cropmask_ar))
			cropmask_bar = int((oheight - cropmask_height)/2)
			logger.debug("Cropmask height: \t{0} = {1} / {2} = {3} left".format(cropmask_height, oheight, cropmask_ar, cropmask_bar))
			
			cropmask_buf = oiio.ImageBuf(oiio.ImageSpec(owidth, oheight, 4, oiio.UINT16))
			
			# Fill with black, alpha = cropmask opacity
			oiio.ImageBufAlgo.fill(cropmask_buf, (0, 0, 0, cropmask_opacity))

			# Fill center with black
			oiio.ImageBufAlgo.fill(cropmask_buf, (0, 0, 0, 0), oiio.ROI(0, owidth, cropmask_bar, oheight - cropmask_bar))
			
			# Merge cropmask buf over image
			oiio.ImageBufAlgo.channels(buf, buf, (0,1,2, 1.0))
			buf = oiio.ImageBufAlgo.over(cropmask_buf, buf)
			oiio.ImageBufAlgo.channels(buf, buf, (0,1,2))
	
	# buf.write(os.path.splitext(os.path.split(frame)[-1])[0]+".jpg")
	return buf



# def invoke(args, wait=False):
# 	args = shlex.split(args)
# 	try:
# 		if (wait):
# 			p = Popen(
# 				args, 
# 				stdin = PIPE, stdout = logger.info, stderr = logger.error, close_fds = True)
# 			p.wait()
# 		else:
# 			p = Popen(
# 				args, 
# 				stdin = PIPE, stdout = logger.info, stderr = logger.error, close_fds = True)

# 		(result, error) = p.communicate()
		
	# except CalledProcessError as e:
	# 	logger.error(
	# 		"common::run_command() : [ERROR]: output = %s, error code = %s\n" 
	# 		% (e.output, e.returncode))
	# return result
"""

subprocess with pipe
ps = Popen(('ps', '-A'), stdout=PIPE)
output = check_output(('grep', 'process_name'), stdin=ps.stdout)
ps.wait()

"""


def setup_ffmpeg(globals_config, codec_config):
	"""
		Set up ffmpeg command according to codec config. 
		Return entire command.
	"""

	if codec_config['bitdepth'] >= 10:
		ffmpeg_command = "ffmpeg-10bit"
	else:
		ffmpeg_command = "ffmpeg"

	# Set up input arguments for pipe:
	args = "{0} -y -f rawvideo -pixel_format rgb48le -video_size {1}x{2} -framerate {3} -i pipe:0".format(
		ffmpeg_command, globals_config['width'], globals_config['height'], globals_config['framerate'])
	
	if codec_config['codec']:
		args += " -c:v {0}".format(codec_config['codec'])
	
	if codec_config['profile']:
		args += " -profile:v {0}".format(codec_config['profile'])

	if codec_config['qscale']:
		args += " -qscale:v {0}".format(codec_config['qscale'])

	if codec_config['preset']:
		args += " -preset {0}".format(codec_config['preset'])

	if codec_config['keyint']:
		args += " -g {0}".format(codec_config['keyint'])

	if codec_config['bframes']:
		args += " -bf {0}".format(codec_config['bframes'])

	if codec_config['tune']:
		args += " -tune {0}".format(codec_config['tune'])

	if codec_config['crf']:
		args += " -crf {0}".format(codec_config['crf'])
	
	if codec_config['pix_fmt']:
		args += " -pix_fmt {0}".format(codec_config['pix_fmt'])

	if globals_config['framerate']:
		args += " -r {0}".format(globals_config['framerate'])

	if codec_config['vf']:
		args += " -vf {0}".format(codec_config['vf'])

	if codec_config['vendor']:
		args += " -vendor {0}".format(codec_config['vendor'])

	if codec_config['metadata_s']:
		args += " -metadata:s {0}".format(codec_config['metadata_s'])

	if codec_config['bitrate']:
		args += " -b:v {0}".format(codec_config['bitrate'])

	return args

def remove_framenumbers(filename):
	# Remove frame numbers: assumes frame padding is seperated by a _ or . character
	return re.split("[_\.][0-9\%\#].*", filename)[0]

def get_frames(image_sequence):
	# Get input image sequence and ensure it is existing and set up correctly.
	
	if os.path.isdir(image_sequence):
		# Assume there is only one image sequence in this directory
		frames = glob(image_sequence + "/*")
		dirname = image_sequence
		if frames:
			frames.sort()
			first_file = frames[0]
			dirname, filename = os.path.split(first_file)	
			filename, extension = os.path.splitext(filename)
			filename = remove_framenumbers(filename)
		else:
			logger.error("Could not find any frames to operate on!")
			return None, None, None, None
	elif os.path.isfile(image_sequence):
		# Assume it's the first frame of the image sequence
		dirname, filename = os.path.split(image_sequence)
		filename, extension = os.path.splitext(filename)
		filename = remove_framenumbers(filename)
		frames = glob(os.path.join(dirname, filename) + "*")
	else:
		# Assume this is a %05d or ### image sequence.
		dirname, filename = os.path.split(image_sequence)
		filename, extension = os.path.splitext(filename)
		filename = remove_framenumbers(filename)
		frames = glob(os.path.join(dirname, filename) + "*")	
	

	if not frames:
		logger.error("Could not find any frames to operate on!")
		return None, None, None, None

	frames.sort()
	
	logger.info("\nFound {0} {1} frames named {2} in \n\t{3}".format(len(frames), extension, filename, dirname))

	return dirname, filename, extension, frames


def write_frame(buf, pipe):
	buf.get_pixels(oiio.UINT16).tofile(pipe)
	pipe.close()

def setup():
	# Parse Config File
	DAILIES_CONFIG = os.getenv("DAILIES_CONFIG")
	if not DAILIES_CONFIG:
		DAILIES_CONFIG = "/mnt/cave/dev/__pipeline-tools/generate_dailies/generate_dailies/DAILIES_CONFIG.yaml"

	# Get Config
	if os.path.isfile(DAILIES_CONFIG):
		with open(DAILIES_CONFIG, 'r') as configfile:
			config = yaml.load(configfile)
	else:
		logger.error("Could not find config file {0}".format(DAILIES_CONFIG))
		return

	# Get list of possible output profiles from config.
	output_profiles = config["output_profiles"].keys()
	output_profiles.sort()


	# Parse input arguments
	parser = argparse.ArgumentParser(description='Process given exr image sequence with ocio display, resize and output to stdout.')
	parser.add_argument("-i", "--image_sequence", help="Input exr image sequence. Can be a folder containing images, a path to the first image, a percent 05d path, or a ##### path.")
	parser.add_argument('-p', "--preset", help="Preset name: Possible options are defined in the DAILIES_CONFIG:\n{0}".format("\n\t".join(output_profiles)))
	args = parser.parse_args()

	image_sequence = args.image_sequence
	preset = args.preset

	if not image_sequence:
		image_sequence = os.getcwd()
	if not preset:
		preset = "h264_hq"

	# Get Config dicts for globals and the "codec" preset from the config file
	globals_config = config["globals"]
	codec_config = config["output_profiles"][preset]

	# Set logging detail
	if globals_config['debug']:
		logger.setLevel(logging.DEBUG)
	else:
		logger.setLevel(logging.INFO)

	# Try to get ocio config from $OCIO env-var if it's not defined
	if not globals_config['ocioconfig']:
		if os.getenv("OCIO"):
			globals_config['ocioconfig'] = os.getenv("OCIO")

	# Codec Overrides Globals
	for key, value in codec_config.iteritems():
		if key in globals_config:
			if codec_config[key]:
				globals_config[key] = value

	logger.debug("Got config:\n\tCodec Config:\t{0}\n\tImage Sequence Path:\n\t\t{1}".format(
		codec_config['name'], image_sequence))


	# Find image sequence to operate on
	dirname, filename, extension, frames = get_frames(image_sequence)
	if not frames:
		logger.error("Error: No frames found...")
		return

	# If output width or height is not defined, we need to calculate it from the input
	owidth = globals_config['width']
	oheight = globals_config['height']
	if not owidth or not oheight:
		buf = oiio.ImageBuf(frames[0])
		spec = buf.spec()
		iar = float(spec.width) / float(spec.height)
		if not owidth:
			owidth = spec.width
			globals_config['width'] = owidth
		if not oheight:
			oheight = int(round(owidth / iar))
			globals_config['height'] = oheight

	args = setup_ffmpeg(globals_config, codec_config)

	# Append output movie file to args
	# args += " {0}".format(os.path.join(dirname, filename) + ".mov")
	args += " {0}".format(dirname + ".mov")

	logger.debug("Constructed ffmpeg command:\n\t{0}".format(args))

	# invoke(args, wait=True)
	args = shlex.split(args)

	ffproc = Popen(args,
		stdin=PIPE,
		stdout=PIPE)
	for frame in frames:
		buf = process_frame(frame, globals_config, codec_config)
		buf.get_pixels(oiio.UINT16).tofile(ffproc.stdin)
		# output = ffproc.stdout.readline()
		# print output.rstrip()
	result = ffproc.communicate()[0]
	print result

	# # with open('cache', 'w+') as cache:
	# ffmpeg_in = None
	# ffmp = Popen(args, stdin = PIPE, stdout = PIPE, bufsize=1)
	# ffmp.wait()

	# # Loop through all frames and process them with oiio, and write them to stdout
	# for frame in frames:
	# 	buf = process_frame(frame, globals_config, codec_config)
	# 	Thread(target=write_frame, args=[buf, ffmp.stdin]).start()
	# 	try: # read output line by line as soon as the child flushes its stdout buffer
	# 	    for line in iter(ffmp.stdout.readline, b''):
	# 	        print line.strip()[::-1] # print reversed lines
	# 	finally:
	# 	    ffmp.stdout.close()
	# 	    ffmp.wait()
	# 	# write_frame(buf, pipe)
	# 	# buf.get_pixels(oiio.UINT16).tofile(cache)
	# 	# (result, error) = ffmp.communicate()
	# 	# print result




if __name__=="__main__":
	setup()


#!/usr/bin/env python
from __future__ import with_statement
from __future__ import print_function
import os, sys, yaml
import OpenImageIO as oiio
import numpy as np
import os, sys, re, argparse, shlex
from glob import glob
import logging
import time
from datetime import timedelta
import subprocess
from tc import Timecode

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
log = logging.getLogger(__name__)


def oiio_transform(buf, xoffset, yoffset):
	# transform an image without filtering
	orig_roi = buf.roi
	buf.specmod().x += xoffset
	buf.specmod().y += yoffset
	buf_trans = oiio.ImageBuf()
	oiio.ImageBufAlgo.crop(buf_trans, buf, orig_roi)
	return buf_trans


def process_frame(frame, framenumber, globals_config, codec_config):
	"""
		Apply all color and reformat operations to input image, then write the frame to stdout
	"""

	# Setup image buffer
	buf = oiio.ImageBuf(frame)
	spec = buf.spec()
	
	# Get Codec Config and gather information
	iwidth = spec.width
	iheight = spec.height
	iar = float(iwidth) / float(iheight)

	bitdepth = codec_config['bitdepth']
	if bitdepth > 8:
		pixel_data_type = oiio.UINT16
	else:
		pixel_data_type = oiio.UINT8

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
			log.info("Got crop percentage: {0}".format(cropwidth))
		if "%" in cropheight:
			cropheight = int(float(cropheight.split('%')[0])/100*iheight)
			log.info("Got crop percentage: {0}".format(cropheight))

		buf = oiio.ImageBufAlgo.crop(buf, roi=oiio.ROI(cropwidth / 2, iwidth - cropwidth / 2, cropheight / 2, iheight - cropheight / 2))
		# buf.set_full(cropwidth / 2, iwidth - cropwidth / 2, cropheight / 2, iheight - cropheight / 2, 0, 0)

		log.debug("CROPPED:{0} {1}".format(buf.spec().width, buf.spec().height))

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
		log.info("Performing Resize: \n\tinput: {0}x{1} ar{2}\n\toutput: {3}x{4} ar{5}".format(iwidth, iheight, iar, owidth, oheight, oar))

		if iwidth != owidth:
			# Perform resize, no change in AR
			log.debug("{0}, {1}".format(oheight_noar, px_filter))
			if px_filter:
				# (bug): using "lanczos3", 6.0, and upscaling causes artifacts
				# (bug): dst buf must be assigned or ImageBufAlgo.resize doesn't work
				buf = oiio.ImageBufAlgo.resize(buf, px_filter, roi=oiio.ROI(0, owidth, 0, oheight_noar))
			else:
				buf = oiio.ImageBufAlgo.resize(buf, roi=oiio.ROI(0, owidth, 0, oheight_noar))
				
		if fit:
			# # If fitting is enabled..
			height_diff = oheight - oheight_noar
			log.debug("Height difference: {0} {1} {2}".format(height_diff, oheight, oheight_noar))

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
			log.debug("Cropmask height: \t{0} = {1} / {2} = {3} left".format(cropmask_height, oheight, cropmask_ar, cropmask_bar))
			
			cropmask_buf = oiio.ImageBuf(oiio.ImageSpec(owidth, oheight, 4, pixel_data_type))
			
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


def setup_ffmpeg(globals_config, codec_config, start_tc):
	"""
		Set up ffmpeg command according to codec config. 
		Return entire command.
	"""

	if codec_config['bitdepth'] >= 10:
		ffmpeg_command = "ffmpeg-10bit"
		pixel_format = "rgb48le"
	else:
		ffmpeg_command = "ffmpeg"
		pixel_format = "rgb24"

	# Set up input arguments for pipe:
	args = "{0} -y -f rawvideo -pixel_format {1} -video_size {2}x{3} -framerate {4} -i pipe:0".format(
		ffmpeg_command, pixel_format, globals_config['width'], globals_config['height'], globals_config['framerate'])
	
	# Add timecode so that start frame will display correctly in RV etc
	args += " -timecode {0}".format(start_tc)
	
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

def parse_framenumbers(filename):
	# Remove frame numbers: assumes frame padding is seperated by a _ or . character
	# Takes a file name as input - no absolute paths!
	filename_base = re.split("[_\.][0-9\%\#].*", filename)
	if filename_base:
		filename_base = filename_base[0]
	log.debug("FILENAME BASE" + str(filename_base))
	filename_noext = os.path.splitext(os.path.split(filename)[-1])[0]
	
	log.debug("FILENAME NOEXT" + str(filename_noext))
	framenumber = re.findall("[_\.][0-9].*$", filename_noext)
	if framenumber:
		# Chop off the separater at the beginning of the framenumber
		framenumber = framenumber[0][1:]
		try:
			framenumber = int(framenumber)
			log.debug(framenumber)
		except:
			log.error("Could not convert frame number {0} to int!".format(framenumber))
			return None, None
	else:
		framenumber = None

	return filename_base, framenumber


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
			filename = parse_framenumbers(filename)[0]
		else:
			log.error("Could not find any frames to operate on!")
			return None, None, None, None
	elif os.path.isfile(image_sequence):
		# Assume it's the first frame of the image sequence
		dirname, filename = os.path.split(image_sequence)
		filename, extension = os.path.splitext(filename)
		filename = parse_framenumbers(filename)[0]
		frames = glob(os.path.join(dirname, filename) + "*")
	else:
		# Assume this is a %05d or ### image sequence.
		dirname, filename = os.path.split(image_sequence)
		filename, extension = os.path.splitext(filename)
		filename = parse_framenumbers(filename)[0]
		print(os.path.join(dirname, filename))
		frames = glob(os.path.join(dirname, filename) + "*")	
	
	if not frames:
		log.error("Could not find any frames to operate on!")
		return None, None, None, None
	frames.sort()
	known_extensions = ["tiff", "tif", "jpg", "jpeg", "exr", "png", "jp2", "j2c", "tga"]
	# Create a tuple of (path, number) for each frame
	frame_tuples = []
	for frame in frames:
		if os.path.splitext(frame)[-1].split('.')[-1] in known_extensions:
			filename = os.path.split(frame)[-1]
			filename = os.path.splitext(filename)[0]
			filename, framenumber = parse_framenumbers(filename)
			frame_tuples.append((frame, framenumber))
			
	print("FILENAME", filename)

	log.info("\nFound {0} {1} frames named {2} in \n\t{3}".format(len(frames), extension, filename, dirname))

	return dirname, filename, extension, frame_tuples


def setup():
	start_time = time.time()
	# Parse Config File
	DAILIES_CONFIG = os.getenv("DAILIES_CONFIG")
	if not DAILIES_CONFIG:
		DAILIES_CONFIG = "/mnt/cave/dev/__pipeline-tools/generate_dailies/generate_dailies/DAILIES_CONFIG.yaml"

	# Get Config
	if os.path.isfile(DAILIES_CONFIG):
		with open(DAILIES_CONFIG, 'r') as configfile:
			config = yaml.load(configfile)
	else:
		print("Error: Could not find config file {0}".format(DAILIES_CONFIG))
		return

	# Get list of possible output profiles from config.
	output_codecs = config["output_codecs"].keys()
	output_codecs.sort()


	# Parse input arguments
	parser = argparse.ArgumentParser(description='Process given exr image sequence with ocio display, resize and output to stdout.')
	parser.add_argument("-i", "--image_sequence", help="Input exr image sequence. Can be a folder containing images, a path to the first image, a percent 05d path, or a ##### path.")
	parser.add_argument('-c', "--codec", help="Codec name: Possible options are defined in the DAILIES_CONFIG:\n{0}".format("\n\t".join(output_codecs)))
	args = parser.parse_args()

	image_sequence = args.image_sequence
	codec = args.codec

	# Validate codec
	if codec not in output_codecs:
		print("Error: invalid codec specified. Possible options are \n\t{0}".format("\n\t".join(output_codecs)))
		return

	if not image_sequence:
		image_sequence = os.getcwd()
	if not codec:
		codec = "h264_hq"

	# Get Config dicts for globals and the "codec" codec from the config file
	globals_config = config["globals"]
	codec_config = config["output_codecs"][codec]


	# Try to get ocio config from $OCIO env-var if it's not defined
	if not globals_config['ocioconfig']:
		if os.getenv("OCIO"):
			globals_config['ocioconfig'] = os.getenv("OCIO")

	# Codec Overrides Globals
	for key, value in codec_config.iteritems():
		if key in globals_config:
			if codec_config[key]:
				globals_config[key] = value

	# Find image sequence to operate on
	dirname, filename, extension, frames = get_frames(image_sequence)
	if not frames:
		print("Error: No frames found...")
		return

	# If output width or height is not defined, we need to calculate it from the input
	owidth = globals_config['width']
	oheight = globals_config['height']
	if not owidth or not oheight:
		buf = oiio.ImageBuf(frames[0][0])
		spec = buf.spec()
		iar = float(spec.width) / float(spec.height)
		if not owidth:
			owidth = spec.width
			globals_config['width'] = owidth
		if not oheight:
			oheight = int(round(owidth / iar))
			globals_config['height'] = oheight

	# Set up timecode and start / end frames 
	firstframe = frames[0][1]
	lastframe = frames[-1][1]
	totalframes = len(frames)

	tc = Timecode(globals_config['framerate'], start_timecode='00:00:00:00')
	start_tc = tc + firstframe

	bitdepth = codec_config['bitdepth']
	if bitdepth > 8:
		pixel_data_type = oiio.UINT16
	else:
		pixel_data_type = oiio.UINT8

	# Set up ffmpeg command
	args = setup_ffmpeg(globals_config, codec_config, start_tc)
	
	# Append output movie file to ffmpeg command
	movie_ext = globals_config['movie_ext']
	
	# Append codec to dailies movie name if requested
	if globals_config['movie_append_codec']:
		movie_ext = "_" + codec_config['name'] + "." + movie_ext
	movie_name = filename + movie_ext
	args += " {0}".format(os.path.join(dirname, globals_config['movie_location']) + movie_name)

	# Setup logger
	logpath = os.path.join(dirname, globals_config['movie_location']) + os.path.splitext(movie_name)[0] + ".log"
	if os.path.exists(logpath):
		os.remove(logpath)
	handler = logging.FileHandler(logpath)
	handler.setFormatter(
		logging.Formatter('%(levelname)s %(asctime)s \t%(message)s', '%Y-%m-%dT%H:%M:%S')
		)
	log.addHandler(handler)
	if globals_config['debug']:
		log.setLevel(logging.DEBUG)
	else:
		log.setLevel(logging.INFO)
	log.debug("Got config:\n\tCodec Config:\t{0}\n\tImage Sequence Path:\n\t\t{1}".format(
		codec_config['name'], image_sequence))


	log.info("ffmpeg command:\n\t{0}".format(args))
	
			
	# Invoke ffmpeg subprocess
	ffproc = subprocess.Popen(shlex.split(args),
		stdin=subprocess.PIPE,
		stdout=subprocess.PIPE)


	# Loop through every frame, passing the result to the ffmpeg subprocess
	for i, frame in enumerate(frames, 1):
		framepath, framenumber = frame
		log.info("Processing frame {0:04d}: \t{1:04d} of {2:04d}".format(framenumber, i, totalframes))
		# elapsed_time = timedelta(seconds = time.time() - start_time)
		# log.info("Time Elapsed: \t{0}".format(elapsed_time))
	
		buf = process_frame(framepath, framenumber, globals_config, codec_config)
		buf.get_pixels(pixel_data_type).tofile(ffproc.stdin)

	result, error = ffproc.communicate()
	elapsed_time = timedelta(seconds = time.time() - start_time)
	log.info("Total Processing Time: \t{0}".format(elapsed_time))



if __name__=="__main__":
	setup()


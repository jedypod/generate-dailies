#!/usr/bin/env python
from __future__ import with_statement
import os, sys, yaml
import OpenImageIO as oiio
import numpy as np
import os, sys, re, argparse
import shlex, subprocess
from glob import glob

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





def write_frame(buf):
	# Write the passed image buffer to stdout
	buf.get_pixels(oiio.UINT16).tofile(sys.stdout)


def process_frame(frame, globals_config, codec_config):
	"""
		Apply all color and reformat operations to input image, then write the frame to stdout
	"""
	
	# Get Codec Config
	owidth = globals_config['width']
	oheight = globals_config['height']
	fit = globals_config['fit']

	# Setup image buffer
	buf = oiio.ImageBuf(frame)
	spec = buf.spec()

	# Remove alpha channel
	oiio.ImageBufAlgo.channels(buf, buf, (0,1,2))

	# Apply OCIO Display
	ocioconfig = global_config['ocioconfig']
	ociocolorconvert = global_config['ociocolorconvert']
	ociolook = global_config['ociolook']
	ociodisplay = global_config['ociodisplay']
	ocioview = global_config['ocioview']
	if ocioconfig:
		if ociocolorconvert:
			oiio.ImageBufAlgo.ociocolorconvert(buf, buf, ociocolorconvert, ocioview, colorconfig=ocioconfig)
		if ociolook:
			oiio.ImageBufAlgo.ociolook(buf, buf, ociolook, ocioview, colorconfig=ocioconfig)
		if ociodisplay and ocioview: 
			# Apply OCIO display transform onto specified image buffer
			oiio.ImageBufAlgo.ociodisplay(buf, buf, ociodisplay, ocioview, colorconfig=ocioconfig)

	# Apply Resize / Fit
	iwidth = spec.width
	iheight = spec.height
	iar = iwidth / iheight
	if 
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
	# write_frame(buf)



def invoke(args, wait=False):
	args = shlex.split(args)
	try:
		if (wait):
			p = subprocess.Popen(
				args, 
				stdout = subprocess.PIPE)
			p.wait()
		else:
			p = subprocess.Popen(
				args, 
				stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = None, close_fds = True)

		(result, error) = p.communicate()
		
	except subprocess.CalledProcessError as e:
		sys.stderr.write(
			"common::run_command() : [ERROR]: output = %s, error code = %s\n" 
			% (e.output, e.returncode))
	return result 
"""

subprocess with pipe
ps = subprocess.Popen(('ps', '-A'), stdout=subprocess.PIPE)
output = subprocess.check_output(('grep', 'process_name'), stdin=ps.stdout)
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
	args = "{0} -f rawvideo -pixel_format rgb48le -video_size {1}x{2} -framerate {3} -i pipe:0".format(
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
		args += " -r {0}".format(vframerate)

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
			print "Could not find any frames to operate on!"
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
		print "Could not find any frames to operate on!"
		return None, None, None, None
	
	print "\nFound {0} {1} frames named {2} in \n\t{3}".format(len(frames), extension, filename, dirname)

	return dirname, filename, extension, frames


def setup():
	# Parse Config File
	DAILIES_CONFIG = os.getenv("DAILIES_CONFIG")
	if not DAILIES_CONFIG:
		DAILIES_CONFIG = "/mnt/cave/dev/__pipeline-tools/generate_dailies/generate_dailies/DAILIES_CONFIG.yaml"

	# Get Config
	with open(DAILIES_CONFIG, 'r') as configfile:
		config = yaml.load(configfile)

	# for section in config:
		# print(section)
		# print config[section]
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

	# Try to get ocio config from $OCIO env-var if it's not defined
	if not global_config['ocioconfig']:
		if os.getenv("OCIO"):
			global_config['ocioconfig'] = os.getenv("OCIO")

	# Codec Overrides Globals
	for key, value in codec_config.iteritems():
		if key in globals_config:
			if codec_config[key]:
				globals_config[key] = value

	# Find image sequence to operate on
	dirname, filename, extension, frames = get_frames(image_sequence)
	if not frames:
		print "Error: No frames found..."
		return

	args = setup_ffmpeg(globals_config, codec_config)

	print "\n\t", args

	# invoke(args, wait=True)

	# Loop through all frames and process them with oiio, and write them to stdout
	for frame in frames:
		process(frame, globals_config, codec_config)

	


if __name__=="__main__":
	setup()


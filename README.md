# OpenImageIO / FFMPEG Daily

Tool to pipe openexr images, apply an ocio display, and output through a bash pipe to ffmpeg and encode to mov

Reads from a config file with the ability to set custom codec presets

## Example Usage
	
```
	Process given image sequence with ocio display, resize and output to ffmpeg for encoding into a dailies movie.

	optional arguments:
	  -h, --help            show this help message and exit
	  -i IMAGE_SEQUENCE, --image_sequence IMAGE_SEQUENCE
	                        Input exr image sequence. Can be a folder containing
	                        images, a path to the first image, a percent 05d path,
	                        or a ##### path. If this is not given the tool searches for
	                        images in the current directory to process.
	  -c CODEC, --codec CODEC
	                        Codec name: Possible options are defined in the
	                        DAILIES_CONFIG: Possible options are
								dnxhd_175
								dnxhd_36
								dnxhr_hqx
								h264_hq
								h264_lq
								mjpeg
								prores_422
								prores_422hq
								prores_4444
	# For example
	daily -i /drive/video/20181108/exr/M02-0014/M02-0014_%06d.exr -c h264_hq

```
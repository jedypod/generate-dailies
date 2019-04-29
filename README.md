# OpenImageIO / FFMPEG Daily

## Overview
Daily is a tool to convert scene-linear openexr images into display-referred quicktime movies. It supports uint16 precision and uses OpenColorIO for colorspace conversions. Common dailies movie features like text comments, frame number overlays, slate frames, and shot number overlays are supported. It also supports resize operations, including cropping, scaling, padding, and masking.

Daily uses OpenImageIO >= 2.0 and OpenColorIO for reading exr, and ffmpeg for encoding to quicktime. No temporary files are required.

Daily reads configuration data from a yaml file, and has the ability to create many custom "codec" presets for different output formats. For example, one could have an internal dailies review format that is 2560x1440 10 bit 4:4:4 h264 log, and a deliveries format that is 1920x1080 8 bit 4:2:2 DNxHD.

## Commandline Options

```
	usage: daily [-h] [-c CODEC] [-p PROFILE] [-o OUTPUT] [-t TEXT]
				[-ct COLOR_TRANSFORM] [--ocio OCIO] [-d]
				input_path

	Process given image sequence with ocio display, resize and output to ffmpeg
	for encoding into a dailies movie.

	positional arguments:
	input_path            Input exr image sequence. Can be a folder containing
							images, a path to the first image, a percent 05d path,
							or a ##### path.

	optional arguments:
	-h, --help            show this help message and exit
	-c CODEC, --codec CODEC
							Codec name: Possible options are defined in the
							DAILIES_CONFIG: avc_1440p avc_lq avchq avclq dnxhd_175
							dnxhd_36 dnxhr_hqx hevc hevc_1440p mjpeg prores_422
							prores_422hq prores_4444
	-p PROFILE, --profile PROFILE
							Dailies profile: Choose the settings to use for
							dailies overlays: delivery internal
	-o OUTPUT, --output OUTPUT
							Output directory: Optional override to movie_location
							in the DAILIES_CONFIG. This can be a path relative to
							the image sequence.
	-t TEXT, --text TEXT  Text elements and contents to add: e.g. "artist: Jed
							Smith | comment: this is stupid man|
	-ct COLOR_TRANSFORM, --color_transform COLOR_TRANSFORM
							OCIO Colorspace Conversion preset to use. Specified in
							the dailies config under ocio_profiles. show_log
							tgm_log abr_log otp_log grade oa_log lima_log
	--ocio OCIO           OCIO Colorspace Conversion to use. Specified in the
							dailies config under ocio_profiles. show_log tgm_log
							abr_log otp_log grade oa_log lima_log
	-d, --debug           Set debug to true.


	# Example commands

	## Daily using the "avchd" codec defined in the yaml configuration file. Output to the "movie_location" path specified in the config.
	daily /drive/video/20181108/exr/M02-0014/M02-0014_%06d.exr -c avchq

	## Daily the same exr sequence to a test output directory, using the "hevc_1440p" codec, and a "log" ocio color transform defined in the "ocio_profiles" section of the config.
	daily /drive/video/20181108/exr/ -o ~/tmp/test_output -c hevc_1440p --ocio /path/to/ocio/config.ocio -ct log
```

## Dependencies
- [OpenImageIO](https://github.com/OpenImageIO/oiio) - Python module used for all image and color manipulations. Must be compiled with OpenImageIO support. Must be OpenImageIO >= 2.0
- [ffmpeg](https://ffmpeg.org) - Used for encoding from OpenImageIO to quicktime.
- [Pillow](https://pillow.readthedocs.io/en/stable/) - Optional Python module used for photo jpeg output. Jpegs are encoded using OpenimageIO -> Pillow -> ffmpeg.
- [Numpy](https://www.numpy.org) - Python module used for OpenImageIO pixel data manipulations.
- [PyYAML](https://pyyaml.org/wiki/PyYAML) - Used to read the yaml configuration file.



# The MIT License
Copyright 2019 Jedediah Smith

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# OpenImageIO / FFMPEG Daily

Tool to pipe openexr images, apply an ocio display, and output through a bash pipe to ffmpeg and encode to mov

Reads from a config file with the ability to set custom codec presets

## Example Usage

```
	Process given image sequence with ocio display, resize and output to ffmpeg for encoding into a dailies movie.

	usage: daily [-h] [-c CODEC] [-p PROFILE] [-o OUTPUT] [-t TEXT]
				[-ct COLOR_TRANSFORM] [--ocio OCIO] [-d]
				input_path

	positional arguments:
	input_path            Input exr image sequence. Can be a folder containing
							images, a path to the first image, a percent 05d path,
							or a ##### path.

	optional arguments:
	-h, --help            show this help message and exit
	-c CODEC, --codec CODEC
							Codec name: Possible options are defined in the
							DAILIES_CONFIG: avc_lq avchq avclq dnxhd_175 dnxhd_36
							dnxhr_hqx hevc hevc_hq hevc_lq mjpeg prores_422
							prores_422hq prores_4444
	-p PROFILE, --profile PROFILE
							Dailies profile: Choose the settings to use for
							dailies overlays: delivery internal
	-o OUTPUT, --output OUTPUT
							Output directory: Optional override to movie_location
							in the DAILIES_CONFIG
	-t TEXT, --text TEXT  Text elements and contents to add: e.g. "artist: Jed
							Smith | comment: this is stupid man|
	-ct COLOR_TRANSFORM, --color_transform COLOR_TRANSFORM
							OCIO Colorspace Conversion preset to use. Specified in
							the dailies config under ocio_profiles. grade show_log
	--ocio OCIO           OCIO Colorspace Conversion to use. Specified in the
							dailies config under ocio_profiles. grade show_log
	-d, --debug           Set debug to true.

	# For example
	daily -i /drive/video/20181108/exr/M02-0014/M02-0014_%06d.exr -c avchq

```


# License
## The MIT License
Copyright 2019 Jedediah Smith

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
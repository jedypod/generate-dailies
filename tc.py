#!-*- coding: utf-8 -*-
# The MIT License (MIT)
#
# Copyright (c) 2014 Joshua Banton and PyTimeCode developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


__version__ = '1.2.0'


class Timecode(object):
    """The main timecode class.

    Does all the calculation over frames, so the main data it holds is
    frames, then when required it converts the frames to a timecode by
    using the frame rate setting.

    :param framerate: The frame rate of the Timecode instance. It
      should be one of ['23.98', '24', '25', '29.97', '30', '50', '59.94',
      '60', 'NUMERATOR/DENOMINATOR', ms'] where "ms" equals to 1000 fps.
      Can not be skipped.
      Setting the framerate will automatically set the :attr:`.drop_frame`
      attribute to correct value.
    :param start_timecode: The start timecode. Use this to be able to
      set the timecode of this Timecode instance. It can be skipped and
      then the frames attribute will define the timecode, and if it is also
      skipped then the start_second attribute will define the start
      timecode, and if start_seconds is also skipped then the default value
      of '00:00:00:00' will be used.
      When using 'ms' frame rate, timecodes like '00:11:01.040' use '.040'
      as frame number. When used with other frame rates, '.040' represents
      a fraction of a second. So '00:00:00.040'@25fps is 1 frame.
    :type framerate: str or int or float or tuple
    :type start_timecode: str or None
    :param start_seconds: A float or integer value showing the seconds.
    :param int frames: Timecode objects can be initialized with an
      integer number showing the total frames.
    """

    def __init__(self, framerate, start_timecode=None, start_seconds=None,
                 frames=None):
        self.drop_frame = False
        self.ms_frame = False
        self.fraction_frame = False
        self._int_framerate = None
        self._framerate = None
        self.framerate = framerate

        self.frames = None

        # attribute override order
        # start_timecode > frames > start_seconds
        if start_timecode:
            self.frames = self.tc_to_frames(start_timecode)
        else:
            if frames is not None:  # because 0==False, and frames can be 0
                self.frames = frames
            elif start_seconds is not None:
                if start_seconds == 0:
                    raise ValueError("``start_seconds`` argument can not be 0")
                self.frames = self.float_to_tc(start_seconds)
            else:
                # use default value of 00:00:00:00
                self.frames = self.tc_to_frames('00:00:00:00')

    @property
    def framerate(self):
        """getter for _framerate attribute
        """
        return self._framerate

    @framerate.setter
    def framerate(self, framerate):  # lint:ok
        """setter for the framerate attribute
        :param framerate:
        :return:
        """

        # Convert rational frame rate to float
        numerator = None
        denominator = None

        try:
            if '/' in framerate:
                numerator, denominator = framerate.split('/')
        except TypeError:
            # not a string
            pass

        if isinstance(framerate, tuple):
            numerator, denominator = framerate

        if numerator and denominator:
            framerate = round(float(numerator) / float(denominator), 2)

            if framerate.is_integer():
                framerate = int(framerate)

        # check if number is passed and if so convert it to a string
        if isinstance(framerate, (int, float)):
            framerate = str(framerate)

        # set the int_frame_rate
        if framerate == '29.97':
            self._int_framerate = 30
            self.drop_frame = True
        elif framerate == '59.94':
            self._int_framerate = 60
            self.drop_frame = True
        elif framerate == '23.98':
            framerate = '24'
            self._int_framerate = 24
        elif framerate in ['ms', '1000']:
            self._int_framerate = 1000
            self.ms_frame = True
            framerate = 1000
        elif framerate == 'frames':
            self._int_framerate = 1
        else:
            self._int_framerate = int(float(framerate))

        self._framerate = framerate

    def set_fractional(self, state):
        """Set or unset timecode to be represented with fractional seconds
        :param bool state:
        """
        self.fraction_frame = state

    def set_timecode(self, timecode):
        """Sets the frames by using the given timecode
        """
        self.frames = self.tc_to_frames(timecode)

    def float_to_tc(self, seconds):
        """set the frames by using the given seconds
        """
        return int(seconds * self._int_framerate)

    def tc_to_frames(self, timecode):
        """Converts the given timecode to frames
        """
        hours, minutes, seconds, frames = map(int,
                                              self.parse_timecode(timecode)
                                              )

        if isinstance(timecode, int):
            time_tokens = [hours, minutes, seconds, frames]
            timecode = ':'.join(str(t) for t in time_tokens)

            if self.drop_frame:
                timecode = ';'.join(timecode.rsplit(':', 1))

        ffps = float(self._framerate)

        if self.drop_frame:
            # Number of drop frames is 6% of framerate rounded to nearest
            # integer
            drop_frames = int(round(ffps * .066666))
        else:
            drop_frames = 0

        # We don't need the exact framerate anymore, we just need it rounded to
        # nearest integer
        ifps = self._int_framerate

        # Number of frames per hour (non-drop)
        hour_frames = ifps * 60 * 60

        # Number of frames per minute (non-drop)
        minute_frames = ifps * 60

        # Total number of minutes
        total_minutes = (60 * hours) + minutes

        # Handle case where frames are fractions of a second
        if len(timecode.split('.')) == 2 and not self.ms_frame:
            self.fraction_frame = True
            fraction = timecode.rsplit('.', 1)[1]

            frames = int(round(float('.' + fraction) * ffps))

        frame_number = \
            ((hour_frames * hours) + (minute_frames * minutes) +
             (ifps * seconds) + frames) - \
            (drop_frames * (total_minutes - (total_minutes // 10)))

        frames = frame_number + 1

        return frames

    def frames_to_tc(self, frames):
        """Converts frames back to timecode

        :returns str: the string representation of the current time code
        """
        ffps = float(self._framerate)

        if self.drop_frame:
            # Number of frames to drop on the minute marks is the nearest
            # integer to 6% of the framerate
            drop_frames = int(round(ffps * .066666))
        else:
            drop_frames = 0

        # Number of frames in an hour
        frames_per_hour = int(round(ffps * 60 * 60))
        # Number of frames in a day - timecode rolls over after 24 hours
        frames_per_24_hours = frames_per_hour * 24
        # Number of frames per ten minutes
        frames_per_10_minutes = int(round(ffps * 60 * 10))
        # Number of frames per minute is the round of the framerate * 60 minus
        # the number of dropped frames
        frames_per_minute = int(round(ffps) * 60) - drop_frames

        frame_number = frames - 1

        if frame_number < 0:
            # Negative time. Add 24 hours.
            frame_number += frames_per_24_hours

        # If frame_number is greater than 24 hrs, next operation will rollover
        # clock
        frame_number %= frames_per_24_hours

        if self.drop_frame:
            d = frame_number // frames_per_10_minutes
            m = frame_number % frames_per_10_minutes
            if m > drop_frames:
                frame_number += (drop_frames * 9 * d) + \
                    drop_frames * ((m - drop_frames) // frames_per_minute)
            else:
                frame_number += drop_frames * 9 * d

        ifps = self._int_framerate

        frs = frame_number % ifps
        if self.fraction_frame:
            frs = round(frs / float(ifps), 3)

        secs = (frame_number // ifps) % 60
        mins = ((frame_number // ifps) // 60) % 60
        hrs = (((frame_number // ifps) // 60) // 60)

        return hrs, mins, secs, frs

    def tc_to_string(self, hrs, mins, secs, frs):
        if self.fraction_frame:
            return "{hh:02d}:{mm:02d}:{ss:06.3f}".format(hh=hrs,
                                                         mm=mins,
                                                         ss=secs + frs
                                                         )

        ff = "%02d"
        if self.ms_frame:
            ff = "%03d"

        return ("%02d:%02d:%02d%s" + ff) % (hrs,
                                            mins,
                                            secs,
                                            self.frame_delimiter,
                                            frs)

    @classmethod
    def parse_timecode(cls, timecode):
        """parses timecode string NDF '00:00:00:00' or DF '00:00:00;00' or
        milliseconds/fractionofseconds '00:00:00.000'
        """
        if isinstance(timecode, int):
            indices = range(2, 10, 2)
            hrs, mins, secs, frs = [hex(timecode)[i:i + 2] for i in indices]

        else:
            bfr = timecode.replace(';', ':').replace('.', ':').split(':')
            hrs = int(bfr[0])
            mins = int(bfr[1])
            secs = int(bfr[2])
            frs = int(bfr[3])

        return hrs, mins, secs, frs

    @property
    def frame_delimiter(self):
        """Return correct symbol based on framerate."""
        if self.drop_frame:
            return ';'

        elif self.ms_frame or self.fraction_frame:
            return '.'

        else:
            return ':'

    def __iter__(self):
        return self

    def next(self):
        self.add_frames(1)
        return self

    def back(self):
        self.sub_frames(1)
        return self

    def add_frames(self, frames):
        """adds or subtracts frames number of frames
        """
        self.frames += frames

    def sub_frames(self, frames):
        """adds or subtracts frames number of frames
        """
        self.add_frames(-frames)

    def mult_frames(self, frames):
        """multiply frames
        """
        self.frames *= frames

    def div_frames(self, frames):
        """adds or subtracts frames number of frames"""
        self.frames = self.frames / frames

    def __eq__(self, other):
        """the overridden equality operator
        """
        if isinstance(other, Timecode):
            return self._framerate == other._framerate and \
                self.frames == other.frames
        elif isinstance(other, str):
            new_tc = Timecode(self._framerate, other)
            return self.__eq__(new_tc)
        elif isinstance(other, int):
            return self.frames == other

    def __ge__(self, other):
        """override greater or equal to operator"""
        if isinstance(other, Timecode):
            return self._framerate == other._framerate and \
                self.frames >= other.frames
        elif isinstance(other, str):
            new_tc = Timecode(self._framerate, other)
            return self.frames >= new_tc.frames
        elif isinstance(other, int):
            return self.frames >= other

    def __le__(self, other):
        """override less or equal to operator"""
        if isinstance(other, Timecode):
            return self._framerate == other._framerate and \
                self.frames <= other.frames
        elif isinstance(other, str):
            new_tc = Timecode(self._framerate, other)
            return self.frames <= new_tc.frames
        elif isinstance(other, int):
            return self.frames <= other

    def __add__(self, other):
        """returns new Timecode instance with the given timecode or frames
        added to this one
        """
        # duplicate current one
        tc = Timecode(self._framerate, frames=self.frames)

        if isinstance(other, Timecode):
            tc.add_frames(other.frames)
        elif isinstance(other, int):
            tc.add_frames(other)
        else:
            raise TimecodeError(
                'Type %s not supported for arithmetic.' %
                other.__class__.__name__
            )

        return tc

    def __sub__(self, other):
        """returns new Timecode instance with subtracted value"""
        if isinstance(other, Timecode):
            subtracted_frames = self.frames - other.frames
        elif isinstance(other, int):
            subtracted_frames = self.frames - other
        else:
            raise TimecodeError(
                'Type %s not supported for arithmetic.' %
                other.__class__.__name__
            )

        return Timecode(self._framerate, frames=subtracted_frames)

    def __mul__(self, other):
        """returns new Timecode instance with multiplied value"""
        if isinstance(other, Timecode):
            multiplied_frames = self.frames * other.frames
        elif isinstance(other, int):
            multiplied_frames = self.frames * other
        else:
            raise TimecodeError(
                'Type %s not supported for arithmetic.' %
                other.__class__.__name__
            )

        return Timecode(self._framerate, frames=multiplied_frames)

    def __div__(self, other):
        """returns new Timecode instance with divided value"""
        if isinstance(other, Timecode):
            div_frames = self.frames / other.frames
        elif isinstance(other, int):
            div_frames = self.frames / other
        else:
            raise TimecodeError(
                'Type %s not supported for arithmetic.' %
                other.__class__.__name__
            )

        return Timecode(self._framerate, frames=div_frames)

    def __repr__(self):
        return self.tc_to_string(*self.frames_to_tc(self.frames))

    @property
    def hrs(self):
        hrs, mins, secs, frs = self.frames_to_tc(self.frames)
        return hrs

    @property
    def mins(self):
        hrs, mins, secs, frs = self.frames_to_tc(self.frames)
        return mins

    @property
    def secs(self):
        hrs, mins, secs, frs = self.frames_to_tc(self.frames)
        return secs

    @property
    def frs(self):
        hrs, mins, secs, frs = self.frames_to_tc(self.frames)
        return frs

    @property
    def frame_number(self):
        """returns the 0 based frame number of the current timecode instance
        """
        return self.frames - 1

    @property
    def float(self):
        """returns the seconds as float
        """
        return self.frames / float(self.framerate)

class TimecodeError(Exception):
    """Raised when an error occurred in timecode calculation
    """
    pass

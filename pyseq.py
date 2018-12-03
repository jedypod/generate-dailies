#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------------------------
# Copyright (c) 2011-2017, Ryan Galloway (ryan@rsgalloway.com)
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#  - Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
#  - Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  - Neither the name of the software nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# -----------------------------------------------------------------------------

"""PySeq is a python module that finds groups of items that follow a naming
convention containing a numerical sequence index, e.g. ::

    fileA.001.png, fileA.002.png, fileA.003.png...

and serializes them into a compressed sequence string representing the entire
sequence, e.g. ::

    fileA.1-3.png

It should work regardless of where the numerical sequence index is embedded 
in the name.

Docs and latest version available for download at

   http://github.com/rsgalloway/pyseq
"""

import os
import re
import logging
import warnings
import functools
from glob import glob
from glob import iglob
from datetime import datetime

__version__ = "0.5.1"

# default serialization format string
global_format = '%4l %h%p%t %R'
default_format = '%h%r%t'

# use strict padding on sequences (pad length must match)
# https://github.com/rsgalloway/pyseq/issues/41
strict_pad = True

# regex for matching numerical characters
digits_re = re.compile(r'\d+')

# regex for matching format directives
format_re = re.compile(r'%(?P<pad>\d+)?(?P<var>\w+)')

# character to join explicit frame ranges on
range_join = os.environ.get('PYSEQ_RANGE_SEP', ', ')

__all__ = [
    'SequenceError', 'FormatError', 'Item', 'Sequence', 'diff', 'uncompress',
    'getSequences', 'get_sequences', 'walk'
]

# logging handlers
log = logging.getLogger('pyseq')
log.addHandler(logging.StreamHandler())
log.setLevel(int(os.environ.get('PYSEQ_LOG_LEVEL', logging.INFO)))

# show deprecationWarnings in 2.7+
warnings.simplefilter('always', DeprecationWarning)

# python 3 strings
try:
    unicode = unicode
except NameError:
    str = str
    unicode = str
    bytes = bytes
    basestring = (str,bytes)
else:
    str = str
    unicode = unicode
    bytes = str
    basestring = basestring


def _natural_key(x):
    """ Splits a string into characters and digits.  This helps in sorting file
    names in a 'natural' way.
    """
    return [int(c) if c.isdigit() else c.lower() for c in re.split("(\d+)", x)]


def _ext_key(x):
    """ Similar to '_natural_key' except this one uses the file extension at
    the head of split string.  This fixes issues with files that are named
    similar but with different file extensions:
    This example:
        file.001.jpg
        file.001.tiff
        file.002.jpg
        file.002.tiff
    Would get properly sorted into:
        file.001.jpg
        file.002.jpg
        file.001.tiff
        file.002.tiff
    """
    name, ext = os.path.splitext(x)
    return [ext] + _natural_key(name)


def natural_sort(items):
    return sorted(items, key=_natural_key)


class SequenceError(Exception):
    """Special exception for Sequence errors
    """
    pass


class FormatError(Exception):
    """Special exception for Sequence format errors
    """
    pass


def deprecated(func):
    """Deprecation warning decorator
    """
    def inner(*args, **kwargs):
        warnings.warn("Call to deprecated method {}".format(func.__name__),
                      category=DeprecationWarning, stacklevel=2)
        return func(*args, **kwargs)
    inner.__name__ = func.__name__
    inner.__doc__ = func.__doc__
    inner.__dict__.update(func.__dict__)
    return inner


class Item(str):
    """Sequence member file class

    :param item: Path to file.
    """

    def __init__(self, item):
        super(Item, self).__init__()
        log.debug('adding %s', item)
        self.item = item
        self.__path = getattr(item, 'path', None)
        if self.__path is None:
            self.__path = os.path.abspath(str(item))
        self.__dirname, self.__filename = os.path.split(self.__path)
        self.__digits = digits_re.findall(self.name)
        if self.__digits:
            self.__number = int(self.__digits[-1])
        else:
            self.__number = None
        self.__parts = digits_re.split(self.name)
        self.__stat = None

        # modified by self.is_sibling()
        self.frame = None
        self.head = self.name
        self.tail = ''
        self.pad = None

    def __eq__(self, other):
        return self.path == other.path

    def __ne__(self, other):
        return self.path != other.path

    def __lt__(self, other):
        return self.frame < other.frame

    def __gt__(self, other):
        return self.frame > other.frame

    def __ge__(self, other):
        return self.frame >= other.frame

    def __le__(self, other):
        return self.frame <= other.frame

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return '<pyseq.Item "%s">' % self.name

    def __getattr__(self, key):
        return getattr(self.item, key)

    @property
    def path(self):
        """Item absolute path, if a filesystem item.
        """
        return self.__path

    @property
    def name(self):
        """Item base name attribute
        """
        return self.__filename

    @property
    def dirname(self):
        """"Item directory name, if a filesystem item."
        """
        return self.__dirname

    @property
    def digits(self):
        """Numerical components of item name.
        """
        return self.__digits

    @property
    def number(self):
        """The frame number of the item.
        """
        return self.__number

    @property
    def parts(self):
        """Non-numerical components of item name
        """
        return self.__parts

    @property
    def exists(self):
        """Returns True if this item exists on disk
        """
        return os.path.isfile(self.__path)

    @property
    def size(self):
        """Returns the size of the Item, reported by os.stat
        """
        return self.stat.st_size

    @property
    def mtime(self):
        """Returns the modification time of the Item
        """
        return self.stat.st_mtime

    @property
    def stat(self):
        """ Returns the os.stat object for this file.
        """
        if self.__stat is None:
            self.__stat = os.stat(self.__path)
        return self.__stat

    @deprecated
    def isSibling(self, item):
        """Deprecated: use is_sibling instead
        """
        return self.is_sibling(item)

    def is_sibling(self, item):
        """Determines if this and item are part of the same sequence.

        :param item: An :class:`.Item` instance.

        :return: True if this and item are sequential siblings.
        """
        if not isinstance(item, Item):
            item = Item(item)

        d = diff(self, item)
        is_sibling = (len(d) == 1) and (self.parts == item.parts)

        # I do not understand why we are updating information
        # while this is a predicate method
        if is_sibling:
            frame = d[0]['frames'][0]
            self.frame = int(frame)
            self.pad = len(frame)
            self.head = self.name[:d[0]['start']]
            self.tail = self.name[d[0]['end']:]
            frame = d[0]['frames'][1]
            item.frame = int(frame)
            item.pad = len(frame)
            item.head = item.name[:d[0]['start']]
            item.tail = item.name[d[0]['end']:]

        return is_sibling


class Sequence(list):
    """Extends list class with methods that handle item sequentialness.

    For example:

        >>> s = Sequence(['file.0001.jpg', 'file.0002.jpg', 'file.0003.jpg'])
        >>> print(s)
        file.1-3.jpg
        >>> s.append('file.0006.jpg')
        >>> print(s.format('%4l %h%p%t %R'))
           4 file.%04d.jpg 1-3 6
        >>> s.includes('file.0009.jpg')
        True
        >>> s.includes('file.0009.pic')
        False
        >>> s.contains('file.0006.jpg')
        False
        >>> print(s.format('%h%p%t %r (%R)'))
        file.%04d.jpg 1-6 (1-3 6)
    """

    def __init__(self, items):
        """
        Create a new Sequence class object.

        :param: items: Sequential list of items.

        :return: pyseq.Sequence class instance.
        """
        # otherwise Sequence consumes the list
        items = items[::]
        super(Sequence, self).__init__([Item(items.pop(0))])
        self.__missing = []
        self.__dirty = False
        self.__frames = None

        while items:
            f = Item(items.pop(0))
            try:
                self.append(f)
                log.debug('+Item belongs to sequence.')
            except SequenceError:
                log.debug('-Item does not belong to sequence.')
                continue
            except KeyboardInterrupt:
                log.info("Stopping.")
                break

    def __attrs__(self):
        """Replaces format directives with callables to get their values."""
        return {
            'l': self.length,
            's': self.start,
            'e': self.end,
            'f': self.frames,
            'm': self.missing,
            'M': functools.partial(self._get_framerange, self.missing(), missing=True),
            'd': lambda *x: self.size,
            'D': self.directory,
            'p': self._get_padding,
            'r': functools.partial(self._get_framerange, self.frames(), missing=False),
            'R': functools.partial(self._get_framerange, self.frames(), missing=True),
            'h': self.head,
            't': self.tail
        }

    def __str__(self):
        return self.format(default_format)

    def __repr__(self):
        return '<pyseq.Sequence "%s">' % str(self)

    def __getattr__(self, key):
        return getattr(self[0], key)

    def __contains__(self, item):
        super(Sequence, self).__contains__(Item(item))

    def __setitem__(self, index, item):
        """ Used to set a particular element in the sequence
        """
        if type(item) is not Item:
            item = Item(item)
        if self.includes(item):
            super(Sequence, self).__setitem__(index, item)
            self.__frames = None
            self.__missing = None
        else:
            raise SequenceError("Item is not a member of sequence.")

    def __setslice__(self, start, end, item):
        if isinstance(item, basestring):
            item = Sequence([item])
        if isinstance(item, list) is False:
            raise TypeError("Invalid type to add to sequence")
        for i in item:
            if self.includes(i) is False:
                raise SequenceError("Item (%s) is not a member of sequence."
                                    % i)
        super(Sequence, self).__setslice__(start, end, item)
        self.__frames = None
        self.__missing = None

    def __add__(self, item):
        """ return a new sequence with the item appended.  Accepts an Item,
            a string, or a list.
        """
        if isinstance(item, basestring):
            item = Sequence([item])
        if isinstance(item, list) is False:
            raise TypeError("Invalid type to add to sequence")
        ns = Sequence(self[::])
        ns.extend(item)
        return ns

    def __iadd__(self, item):
        if isinstance(item, basestring) or type(item) is Item:
            item = [item]
        if isinstance(item, list) is False:
            raise TypeError("Invalid type to add to sequence")
        self.extend(item)
        return self

    def format(self, fmt=global_format):
        """Format the stdout string.

        The following directives can be embedded in the format string.
        Format directives support padding, for example: "%04l".

        +-----------+--------------------------------------+
        | Directive | Meaning                              |
        +===========+======================================+
        | ``%s``    | sequence start                       |
        +-----------+--------------------------------------+
        | ``%e``    | sequence end                         |
        +-----------+--------------------------------------+
        | ``%l``    | sequence length                      |
        +-----------+--------------------------------------+
        | ``%f``    | list of found files                  |
        +-----------+--------------------------------------+
        | ``%m``    | list of missing files                |
        +-----------+--------------------------------------+
        | ``%M``    | explicit missingfiles [11-14,19-21]  |
        +-----------+--------------------------------------+
        | ``%p``    | padding, e.g. %06d                   |
        +-----------+--------------------------------------+
        | ``%r``    | implied range, start-end             |
        +-----------+--------------------------------------+
        | ``%R``    | explicit broken range, [1-10, 15-20] |
        +-----------+--------------------------------------+
        | ``%d``    | disk usage                           |
        +-----------+--------------------------------------+
        | ``%D``    | parent directory                     |
        +-----------+--------------------------------------+
        | ``%h``    | string preceding sequence number     |
        +-----------+--------------------------------------+
        | ``%t``    | string after the sequence number     |
        +-----------+--------------------------------------+

        :param fmt: Format string. Default is '%4l %h%p%t %R'.

        :return: Formatted string.
        """
        format_char_types = {
            's': 'i',
            'e': 'i',
            'l': 'i',
            'f': 's',
            'm': 's',
            'M': 's',
            'p': 's',
            'r': 's',
            'R': 's',
            'd': 's',
            'D': 's',
            'h': 's',
            't': 's'
        }

        atts = self.__attrs__()
        for m in format_re.finditer(fmt):
            var = m.group('var')
            pad = m.group('pad')
            try:
                fmt_char = format_char_types[var]
            except KeyError as err:
                raise FormatError("Bad directive: %%%s" % var)
            _old = '%s%s' % (pad or '', var)
            _new = '(%s)%s%s' % (var, pad or '', fmt_char)
            fmt = fmt.replace(_old, _new)
            val = atts[var]
            # only execute the callable once, just in case
            if callable(val):
                val = atts[var]()
                atts[var] = val

        return fmt % atts

    @property
    def mtime(self):
        """Returns the latest mtime of all items
        """
        maxDate = list()
        for i in self:
            maxDate.append(i.mtime)
        return max(maxDate)

    @property
    def size(self):
        """Returns the size all items (divide by 1024*1024 for MBs)
        """
        tempSize = list()
        for i in self:
            tempSize.append(i.size)
        return sum(tempSize)

    def directory(self):
        return self[0].dirname + os.sep

    def length(self):
        """:return: The length of the sequence."""
        return len(self)

    def frames(self):
        """:return: List of files in sequence."""
        if not hasattr(self, '__frames') or not self.__frames or self.__dirty:
            self.__frames = self._get_frames()
            self.__frames.sort()
        return self.__frames

    def start(self):
        """:return: First index number in sequence
        """
        try:
            return self.frames()[0]
        except IndexError:
            return 0

    def end(self):
        """:return: Last index number in sequence
        """
        try:
            return self.frames()[-1]
        except IndexError:
            return 0

    def missing(self):
        """:return: List of missing files."""
        if not hasattr(self, '__missing') or not self.__missing:
            self.__missing = self._get_missing()
        return self.__missing

    def head(self):
        """:return: String before the sequence index number."""
        return self[0].head

    def tail(self):
        """:return: String after the sequence index number."""
        return self[0].tail

    def path(self):
        """:return: Absolute path to sequence."""
        _dirname = str(os.path.dirname(os.path.abspath(self[0].path)))
        return os.path.join(_dirname, str(self))

    def includes(self, item):
        """Checks if the item can be contained in this sequence that is if it
        is a sibling of any of the items in the list

        For example:

            >>> s = Sequence(['fileA.0001.jpg', 'fileA.0002.jpg'])
            >>> print(s)
            fileA.1-2.jpg
            >>> s.includes('fileA.0003.jpg')
            True
            >>> s.includes('fileB.0003.jpg')
            False
        """
        if len(self) > 0:
            if not isinstance(item, Item):
                item = Item(item)
            if self[-1] != item:
                return self[-1].is_sibling(item)
            elif self[0] != item:
                return self[0].is_sibling(item)
            else:
                # it should be the only item in the list
                if self[0] == item:
                    return True

        return True

    def contains(self, item):
        """Checks for sequence membership. Calls Item.is_sibling() and returns
        True if item is part of the sequence.

        For example:

            >>> s = Sequence(['fileA.0001.jpg', 'fileA.0002.jpg'])
            >>> print(s)
            fileA.1-2.jpg
            >>> s.contains('fileA.0003.jpg')
            False
            >>> s.contains('fileB.0003.jpg')
            False

        :param item: pyseq.Item class object.

        :return: True if item is a sequence member.
        """
        if len(self) > 0:
            if not isinstance(item, Item):
                item = Item(item)
            return self.includes(item)\
                and self.end() >= item.frame >= self.start()

        return False

    def append(self, item):
        """Adds another member to the sequence.

        :param item: pyseq.Item object.

        :exc:`SequenceError` raised if item is not a sequence member.
        """
        if type(item) is not Item:
            item = Item(item)

        if self.includes(item):
            super(Sequence, self).append(item)
            self.__frames = None
            self.__missing = None
        else:
            raise SequenceError('Item is not a member of this sequence')

    def insert(self, index, item):
        """ Add another member to the sequence at the given index.
            :param item: pyseq.Item object.
            :exc: `SequenceError` raised if item is not a sequence member.
        """
        if type(item) is not Item:
            item = Item(item)

        if self.includes(item):
            super(Sequence, self).insert(index, item)
            self.__frames = None
            self.__missing = None
        else:
            raise SequenceError("Item is not a member of this sequence.")

    def extend(self, items):
        """ Add members to the sequence.
            :param items: list of pyseq.Item objects.
            :exc: `SequenceError` raised if any items are not a sequence
                  member.
        """
        for item in items:
            if type(item) is not Item:
                item = Item(item)

            if self.includes(item):
                super(Sequence, self).append(item)
                self.__frames = None
                self.__missing = None
            else:
                raise SequenceError("Item (%s) is not a member of this "
                                    "sequence." % item)

    def reIndex(self, offset, padding=None):
        """Renames and reindexes the items in the sequence, e.g. ::

            >>> seq.reIndex(offset=100)

        will add a 100 frame offset to each Item in `seq`, and rename
        the files on disk.

        :param offset: the frame offset to apply to each item
        :param padding: change the padding
        """
        if not padding:
            padding = self.format("%p")

        if offset > 0:
            gen = ((image, frame) for (image, frame) in zip(reversed(self),
                reversed(self.frames())))
        else:
            gen = ((image, frame) for (image, frame) in zip(self, self.frames()))

        for image, frame in gen:
            oldName = image.path
            newFrame = padding % (frame + offset)
            newFileName = "%s%s%s" % (self.format("%h"), newFrame,
                self.format("%t"))
            newName = os.path.join(image.dirname, newFileName)

            try:
                import shutil
                shutil.move(oldName, newName)
            except Exception as err:
                log.error(err)
            else:
                log.debug('renaming %s %s' % (oldName, newName))
                self.__dirty = True
                image.frame = int(newFrame)

        else:
            self.frames()

    def _get_padding(self):
        """:return: padding string, e.g. %07d"""
        try:
            pad = self[0].pad
            if pad is None:
                return ""
            if pad < 2:
                return '%d'
            return '%%%02dd' % pad
        except IndexError:
            return ''

    def _get_framerange(self, frames, missing=True):
        """Returns frame range string, e.g. [1-500].
        
        :param frames: list of ints like [1,4,8,12,15].
        :param missing: Expand sequence to exclude missing sequence indices.

        :return: formatted frame range string.
        """
        frange = []
        start = ''
        end = ''
        if not missing:
            if frames:
                return '%s-%s' % (self.start(), self.end())
            else:
                return ''

        if not frames:
            return ''

        for i in range(0, len(frames)):
            frame = frames[i]
            if i != 0 and frame != frames[i - 1] + 1:
                if start != end:
                    frange.append('%s-%s' % (str(start), str(end)))
                elif start == end:
                    frange.append(str(start))
                start = end = frame
                continue
            if start is '' or int(start) > frame:
                start = frame
            if end is '' or int(end) < frame:
                end = frame
        if start == end:
            frange.append(str(start))
        else:
            frange.append('%s-%s' % (str(start), str(end)))
        return "[%s]" % range_join.join(frange)

    def _get_frames(self):
        """finds the sequence indexes from item names
        """
        return [f.frame for f in self if f.frame is not None]

    def _get_missing(self):
        """Looks for missing sequence indexes in sequence

        .. todo:: change this to:
            r = range(frames[0], frames[-1] + 1)
            return sorted(list(set(frames).symmetric_difference(r)))
        """
        missing = []
        frames = self.frames()
        if len(frames) == 0:
            return missing

        r = range(frames[0], frames[-1] + 1)
        return sorted(list(set(frames).symmetric_difference(r)))


def diff(f1, f2):
    """Examines diffs between f1 and f2 and deduces numerical sequence number.

    For example ::

        >>> diff('file01_0040.rgb', 'file01_0041.rgb')
        [{'frames': ('0040', '0041'), 'start': 7, 'end': 11}]

        >>> diff('file3.03.rgb', 'file4.03.rgb')
        [{'frames': ('3', '4'), 'start': 4, 'end': 5}]

    :param f1: pyseq.Item object.
    :param f2: pyseq.Item object, for comparison.

    :return: Dictionary with keys: frames, start, end.
    """
    log.debug('diff: %s %s' % (f1, f2))
    if not type(f1) == Item:
        f1 = Item(f1)
    if not type(f2) == Item:
        f2 = Item(f2)

    l1 = [m for m in digits_re.finditer(f1.name)]
    l2 = [m for m in digits_re.finditer(f2.name)]

    d = []
    if len(l1) == len(l2):
        for i in range(0, len(l1)):
            m1 = l1.pop(0)
            m2 = l2.pop(0)
            if (m1.start() == m2.start()) and (m1.group() != m2.group()):
                if strict_pad is True and (len(m1.group()) != len(m2.group())):
                    continue
                d.append({
                    'start': m1.start(),
                    'end': m1.end(),
                    'frames': (m1.group(), m2.group())
                })

    log.debug(d)
    return d


def uncompress(seq_string, fmt=global_format):
    """Basic uncompression or deserialization of a compressed sequence string.

    For example: ::

        >>> seq = uncompress('./tests/files/012_vb_110_v001.%04d.png 1-10', fmt='%h%p%t %r')
        >>> print(seq)
        012_vb_110_v001.1-10.png
        >>> len(seq)
        10
        >>> seq2 = uncompress('./tests/files/a.%03d.tga [1-3, 10, 12-14]', fmt='%h%p%t %R')
        >>> print(seq2)
        a.1-14.tga
        >>> len(seq2)
        7
        >>> seq3 = uncompress('a.%03d.tga 1-14 ([1-3, 10, 12-14])', fmt='%h%p%t %r (%R)')
        >>> print(seq3)
        a.1-14.tga
        >>> len(seq3)
        7

    See unit tests for more examples.

    :param seq_string: Compressed sequence string.
    :param fmt: Format of sequence string.

    :return: :class:`.Sequence` instance.
    """
    dirname = os.path.dirname(seq_string)
    # remove directory
    if "%D" in fmt:
        fmt = fmt.replace("%D", "")
    name = os.path.basename(seq_string)
    log.debug('uncompress: %s' % name)

    # map of directives to regex
    remap = {
        's': '\d+',
        'e': '\d+',
        'l': '\d+',
        'h': '(\S+)?',
        't': '(\S+)?',
        'r': '\d+-\d+',
        'R': '\[[\d\s?\-%s?]+\]' % re.escape(range_join),
        'p': '%\d+d',
        'm': '\[.*\]',
        'f': '\[.*\]',
    }

    log.debug('fmt in: %s' % fmt)

    # escape any re chars in format
    fmt = re.escape(fmt)

    # replace \% with % back again
    fmt = fmt.replace('\\%', '%')

    log.debug('fmt escaped: %s' % fmt)

    for m in format_re.finditer(fmt):
        _old = '%%%s%s' % (m.group('pad') or '', m.group('var'))
        _new = '(?P<%s>%s)' % (
            m.group('var'),
            remap.get(m.group('var'), '\w+')
        )
        fmt = fmt.replace(_old, _new)

    log.debug('fmt: %s' % fmt)

    regex = re.compile(fmt)
    match = regex.match(name)

    log.debug("match: %s" % match.groupdict() if match else "")

    frames = []
    missing = []
    s = None
    e = None

    if not match:
        log.debug('No matches.')
        return

    try:
        pad = match.group('p')

    except IndexError:
        pad = "%d"

    try:
        R = match.group('R')
        R = R[1:-1]
        number_groups = R.split(range_join)
        pad_len = 0
        for number_group in number_groups:
            if '-' in number_group:
                splits = number_group.split('-')
                pad_len = max(pad_len, len(splits[0]), len(splits[1]))
                start = int(splits[0])
                end = int(splits[1])
                frames.extend(range(start, end + 1))

            else:
                end = int(number_group)
                pad_len = max(pad_len, len(number_group))
                frames.append(end)
        if pad == "%d" and pad_len != 0:
            pad = "%0" + str(pad_len) + "d"

    except IndexError:
        try:
            r = match.group('r')
            s, e = r.split('-')
            frames = range(int(s), int(e) + 1)

        except IndexError:
            s = match.group('s')
            e = match.group('e')

    try:
        frames = eval(match.group('f'))

    except IndexError:
        pass

    try:
        missing = eval(match.group('m'))

    except IndexError:
        pass

    items = []
    if missing:
        for i in range(int(s), int(e) + 1):
            if i in missing:
                continue
            f = pad % i
            name = '%s%s%s' % (
                match.groupdict().get('h', ''), f, 
                match.groupdict().get('t', '')
            )
            items.append(Item(os.path.join(dirname, name)))

    else:
        for i in frames:
            f = pad % i
            name = '%s%s%s' % (
                match.groupdict().get('h', ''), f, 
                match.groupdict().get('t', '')
            )
            items.append(Item(os.path.join(dirname, name)))

    seqs = get_sequences(items)
    if seqs:
        return seqs[0]
    return seqs


@deprecated
def getSequences(source):
    """Deprecated: use get_sequences instead
    """
    return get_sequences(source)


def get_sequences(source):
    """Returns a list of Sequence objects given a directory or list that contain
    sequential members.

    Get sequences in a directory:

        >>> seqs = get_sequences('./tests/files/')
        >>> for s in seqs: print(s)
        ...
        012_vb_110_v001.1-10.png
        012_vb_110_v002.1-10.png
        a.1-14.tga
        alpha.txt
        bnc01_TinkSO_tx_0_ty_0.101-105.tif
        bnc01_TinkSO_tx_0_ty_1.101-105.tif
        bnc01_TinkSO_tx_1_ty_0.101-105.tif
        bnc01_TinkSO_tx_1_ty_1.101-105.tif
        file.1-2.tif
        file.info.03.rgb
        file01_40-43.rgb
        file02_44-47.rgb
        file1-4.03.rgb
        file_02.tif
        z1_001_v1.1-4.png
        z1_002_v1.1-4.png
        z1_002_v2.1-4.png

    Get sequences from a list of file names:

        >>> seqs = get_sequences(['fileA.1.rgb', 'fileA.2.rgb', 'fileB.1.rgb'])
        >>> for s in seqs: print(s)
        ...
        fileA.1-2.rgb
        fileB.1.rgb

    Get sequences from a list of objects, preserving object attrs:

        >>> seqs = get_sequences(repo.files())
        >>> seqs[0].date
        datetime.datetime(2011, 3, 21, 17, 31, 24)

    :param source: Can be directory path, list of strings, or sortable list of objects.

    :return: List of pyseq.Sequence class objects.
    """
    start = datetime.now()

    # list for storing sequences to be returned later
    seqs = []

    if isinstance(source, list):
        items = sorted(source, key=lambda x: str(x))

    elif isinstance(source, basestring):
        if os.path.isdir(source):
            items = sorted(glob(os.path.join(source, '*')))
        else:
            items = sorted(glob(source))

    else:
        raise TypeError('Unsupported format for source argument')

    log.debug('Found %s files' % len(items))

    # organize the items into sequences
    while items:
        item = Item(items.pop(0))
        found = False
        for seq in seqs[::-1]:
            if seq.includes(item):
                seq.append(item)
                found = True
                break
        if not found:
            seq = Sequence([item])
            seqs.append(seq)

    log.debug('time: %s' % (datetime.now() - start))

    return list(seqs)


def iget_sequences(source):
    """ Generator version of get_sequences.  Creates Sequences from a various
    source files.  A notable difference is the sort order of iget_sequences
    versus get_sequences.  iget_sequences uses an adaption of natural sorting
    that starts with the file extension.  Because of this, Sequences are
    returned ordered by their file extension.

    Get sequences in a directory:

        >>> seqs = iget_sequences('./tests/files/')
        >>> for s in seqs: print(s)
        ...
        file01.1-4.j2k
        fileA.1-3.jpg
        012_vb_110_v001.1-10.png
        012_vb_110_v002.1-10.png
        fileA.1-3.png
        z1_001_v1.1-4.png
        z1_002_v1.1-4.png
        z1_002_v2.1-4.png
        file1.03.rgb
        file01_40-43.rgb
        file2.03.rgb
        file02_44-47.rgb
        file3-4.03.rgb
        file.info.03.rgb
        a.1-14.tga
        bnc01_TinkSO_tx_0_ty_0.101-105.tif
        bnc01_TinkSO_tx_0_ty_1.101-105.tif
        bnc01_TinkSO_tx_1_ty_0.101-105.tif
        bnc01_TinkSO_tx_1_ty_1.101-105.tif
        file.1-2.tif
        file_02.tif
        alpha.txt

    Get sequences from a list of file names:

        >>> seqs = iget_sequences(['fileA.1.rgb', 'fileA.2.rgb', 'fileB.1.rgb'])
        >>> for s in seqs: print(s)
        ...
        fileA.1-2.rgb
        fileB.1.rgb


    :param source: Can be directory path, list of strings, or sortable list of objects.

    :return: List of pyseq.Sequence class objects.
    """
    start = datetime.now()
    if isinstance(source, list):
        items = source
    elif isinstance(source, str):
        if os.path.isdir(source):
            join = os.path.join
            items = [join(source, x) for x in os.listdir(source)]
        else:
            items = iglob(source)
    else:
        raise TypeError("Unsupported format for source argument")

    items = sorted(items, key=_ext_key)
    log.debug("Found %d files", len(items))

    seq = None
    while items:
        item = Item(items.pop(0))
        if seq is None:
            seq = Sequence([item])
        elif seq.includes(item):
            seq.append(item)
        else:
            yield seq
            seq = Sequence([item])

    if seq is not None:
        yield seq
    log.debug("time: %s", datetime.now() - start)


def walk(source, level=-1, topdown=True, onerror=None, followlinks=False, hidden=False):
    """Generator that traverses a directory structure starting at
    source looking for sequences.

    :param source: valid folder path to traverse
    :param level: int, if < 0 traverse entire structure otherwise
                  traverse to given depth
    :param topdown: walk from the top down
    :param onerror: callable to handle os.listdir errors
    :param followlinks: whether to follow links
    :param hidden: include hidden files and dirs
    """
    start = datetime.now()
    assert isinstance(source, basestring) is True
    assert os.path.exists(source) is True
    source = os.path.abspath(source)

    for root, dirs, files in os.walk(source, topdown, onerror, followlinks):

        if not hidden:
            files = [f for f in files if not f[0] == '.']
            dirs[:] = [d for d in dirs if not d[0] == '.']

        files = [os.path.join(root, f) for f in files]

        if topdown is True:
            parts = root.replace(source, "").split(os.sep)
            while "" in parts:
                parts.remove("")
            if len(parts) == level - 1:
                del dirs[:]

        yield root, dirs, get_sequences(files)

    log.debug('time: %s' % (datetime.now() - start))

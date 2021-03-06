'''Utility functions for Pyrocko.'''

import time, logging, os, sys, re, calendar, math, fnmatch, errno, fcntl, shlex, optparse
from scipy import signal
import os.path as op
import numpy as num
import platform

if platform.system() != 'Darwin':
    import util_ext
else:
    util_ext = None


logger = logging.getLogger('pyrocko.util')

try:
    import progressbar as progressbar_mod
except:
    from pyrocko import dummy_progressbar as progressbar_mod

def progressbar_module():
    return progressbar_mod

def setup_logging(programname='pyrocko', levelname='warning'):
    '''Initialize logging.
    
    :param programname: program name to be written in log
    :param levelname: string indicating the logging level ('debug', 'info', 
        'warning', 'error', 'critical')
    
    This function is called at startup by most pyrocko programs to set up a 
    consistent logging format. This is simply a shortcut to a call to
    :py:func:`logging.basicConfig()`.
    '''

    levels = {'debug': logging.DEBUG,
              'info': logging.INFO,
              'warning': logging.WARNING,
              'error': logging.ERROR,
              'critical': logging.CRITICAL}

    logging.basicConfig(
        level=levels[levelname],
        format = programname+':%(name)-20s - %(levelname)-8s - %(message)s' )

def data_file(fn):
    return os.path.join(os.path.split(__file__)[0], 'data', fn)


class DownloadError(Exception):
    pass


def download_file(url, fpath):
    import urllib2

    logger.info('starting download of %s' % url)

    ensuredirs(fpath)
    try:
        f = urllib2.urlopen(url)
    except urllib2.HTTPError, e:
        raise DownloadError('cannot download file from url %s: %s' % (url, e))

    fpath_tmp = fpath + '.%i.temp' % os.getpid()
    g = open(fpath_tmp, 'wb')
    while True:
        data = f.read(1024)
        if not data:
            break
        g.write(data)

    g.close()
    f.close()

    os.rename(fpath_tmp, fpath)

    logger.info('finished download of %s' % url)


if hasattr(num, 'float128'):
    hpfloat = num.float128
elif hasattr(num, 'float96'):
    hpfloat = num.float96
else:
    def hpfloat(x):
        raise Exception('NumPy lacks support for float128 or float96 data type on this platform.')

class Stopwatch:
    '''Simple stopwatch to measure elapsed wall clock time.
    
    Usage::

        s = Stopwatch()
        time.sleep(1)
        print s()
        time.sleep(1)
        print s()
    '''

    def __init__(self):
        self.start = time.time()
    
    def __call__(self):
        return time.time() - self.start
   
def wrap(text, line_length=80):
    '''Paragraph and list-aware wrapping of text.'''
    
    text = text.strip('\n')
    at_lineend = re.compile(r' *\n')
    at_para = re.compile(r'((^|(\n\s*)?\n)(\s+[*] )|\n\s*\n)')
        
    paragraphs =  at_para.split(text)[::5]
    listindents = at_para.split(text)[4::5]
    newlist = at_para.split(text)[3::5]
   
    listindents[0:0] = [None]
    listindents.append(True)
    newlist.append(None)
  
    det_indent = re.compile(r'^ *')
    
    iso_latin_1_enc_failed = False
    outlines = []
    for ip, p in enumerate(paragraphs):
        if not p:
            continue
        
        if listindents[ip] is None:
            _indent = det_indent.findall(p)[0]
            findent = _indent
        else:
            findent = listindents[ip]
            _indent = ' '* len(findent)
        
        ll = line_length - len(_indent)
        llf = ll
        
        oldlines = [ s.strip() for s in at_lineend.split(p.rstrip()) ]
        p1 = ' '.join( oldlines )
        possible = re.compile(r'(^.{1,%i}|.{1,%i})( |$)' % (llf, ll))
        for imatch, match in enumerate(possible.finditer(p1)):
            parout = match.group(1)
            if imatch == 0:
                outlines.append(findent + parout)
            else:
                outlines.append(_indent + parout)
            
        if ip != len(paragraphs)-1 and (listindents[ip] is None or newlist[ip] is not None or listindents[ip+1] is None):
            outlines.append('')
    
    return outlines

class BetterHelpFormatter(optparse.IndentedHelpFormatter):

    def __init__(self, *args, **kwargs):
        optparse.IndentedHelpFormatter.__init__(self, *args, **kwargs)

    def format_option(self, option):
        '''From IndentedHelpFormatter but using a different wrap method.'''

        help_text_position = 4 + self.current_indent
        help_text_width = self.width - help_text_position
       
        opts = self.option_strings[option]
        opts = "%*s%s" % (self.current_indent, "", opts)
        if option.help:
            help_text = self.expand_default(option)

        if self.help_position + len(help_text) + 1 <= self.width:
            lines = [ '', '%-*s %s' % (self.help_position, opts, help_text), '' ]
        else:
            lines = ['']
            lines.append(opts)
            lines.append('')
            if option.help:
                help_lines = wrap(help_text, help_text_width)
                lines.extend(["%*s%s" % (help_text_position, "", line)
                               for line in help_lines])
            lines.append('')

        return "\n".join(lines)

    def format_description(self, description):
        if not description:
            return ''
        
        if self.current_indent == 0:
            lines = []
        else:
            lines = ['']

        lines.extend(wrap(description, self.width - self.current_indent))
        if self.current_indent == 0:
            lines.append('\n')

        return '\n'.join(['%*s%s' % (self.current_indent, '', line) for line in lines]) 


def progressbar(label, maxval):
    widgets = [label, ' ',
            progressbar_mod.Bar(marker='-',left='[',right=']'), ' ',
            progressbar_mod.Percentage(), ' ',]
       
    pbar = progressbar_mod.ProgressBar(widgets=widgets, maxval=maxval).start()
    return pbar

def progress_beg(label):
    '''Notify user that an operation has started.
    
    :param label: name of the operation
    
    To be used in conjuction with :py:func:`progress_end`.
    '''

    sys.stderr.write(label)
    sys.stderr.flush()

def progress_end(label=''):
    '''Notify user that an operation has ended. 
    
    :param label: name of the operation
    
    To be used in conjuction with :py:func:`progress_beg`.
    '''

    sys.stderr.write(' done. %s\n' % label)
    sys.stderr.flush()
        
def polylinefit(x,y, n_or_xnodes):
    '''Fit piece-wise linear function to data.
    
    :param x,y: arrays with coordinates of data
    :param n_or_xnodes: int, number of segments or x coordinates of polyline

    :returns: `(xnodes, ynodes, rms_error)` arrays with coordinates of polyline, root-mean-square error
    '''

    x = num.asarray(x)
    y = num.asarray(y)

    if isinstance(n_or_xnodes, int):
        n = n_or_xnodes
        xmin = x.min()
        xmax = x.max()
        xnodes = num.linspace(xmin, xmax, n+1)
    else:
        xnodes = num.asarray(n_or_xnodes)
        n = xnodes.size - 1

    assert len(x) == len(y)
    assert n > 0

    ndata = len(x)
    a = num.zeros((ndata+(n-1), n*2))
    for i in xrange(n):
        xmin_block = xnodes[i]
        xmax_block = xnodes[i+1]
        if i == n-1:  # don't loose last point
            indices = num.where( num.logical_and(xmin_block <= x, x <= xmax_block) )[0]
        else:
            indices = num.where( num.logical_and(xmin_block <= x, x < xmax_block) )[0]

        a[indices, i*2] = x[indices]
        a[indices, i*2+1] = 1.0

        w = float(ndata)*100.
        if i < n-1:
            a[ndata+i, i*2] = xmax_block*w
            a[ndata+i, i*2+1] = 1.0*w
            a[ndata+i, i*2+2] = -xmax_block*w
            a[ndata+i, i*2+3] = -1.0*w

    d = num.concatenate((y,num.zeros(n-1)))
    model = num.linalg.lstsq(a,d)[0].reshape((n,2))

    ynodes = num.zeros(n+1)
    ynodes[:n] = model[:,0]*xnodes[:n] + model[:,1]
    ynodes[1:] += model[:,0]*xnodes[1:] + model[:,1]
    ynodes[1:n] *= 0.5
    
    rms_error = num.sqrt(num.mean((num.interp(x, xnodes, ynodes) - y)**2))

    return xnodes, ynodes, rms_error

def plf_integrate_piecewise(x_edges, x, y):
    '''Calculate definite integral of piece-wise linear function on intervals.

    Use trapezoidal rule to calculate definite integral of a piece-wise
    linear function for a series of consecutive intervals. `x_edges` and `x`
    must be sorted.

    :param x_edges: array with edges of the intervals
    :param x, y: arrays with coordinates of piece-wise linear function's
                 control points
    '''

    x_all = num.concatenate((x, x_edges))
    ii = num.argsort(x_all)
    y_edges = num.interp(x_edges, x, y)
    y_all = num.concatenate((y, y_edges))
    xs = x_all[ii]
    ys = y_all[ii]
    y_all[ii[1:]] = num.cumsum((xs[1:] - xs[:-1]) * 0.5 * (ys[1:] + ys[:-1]))
    return num.diff(y_all[-len(y_edges):])

class GlobalVars:
    reuse_store = dict()
    decitab_nmax = 0
    decitab = {}
    decimate_fir_coeffs = {}
    decimate_iir_coeffs = {}
    re_frac = None

def decimate_coeffs(q, n=None, ftype='iir'):

    if type(q) != type(1):
        raise Error, "q should be an integer"

    if n is None:
        if ftype == 'fir':
            n = 30
        else:
            n = 8
            
    if ftype == 'fir':
        coeffs = GlobalVars.decimate_fir_coeffs
        if (n, 1./q) not in coeffs:
            coeffs[n,1./q] = signal.firwin(n+1, 1./q, window='hamming')
        
        b = coeffs[n,1./q]
        return b, [1.], n 

    else:
        coeffs = GlobalVars.decimate_iir_coeffs
        if (n,0.05,0.8/q) not in coeffs:
            coeffs[n,0.05,0.8/q] = signal.cheby1(n, 0.05, 0.8/q)
           
        b, a = coeffs[n,0.05,0.8/q]
        return b, a, n


def decimate(x, q, n=None, ftype='iir', zi=None, ioff=0):
    """Downsample the signal x by an integer factor q, using an order n filter
    
    By default, an order 8 Chebyshev type I filter is used or a 30 point FIR 
    filter with hamming window if ftype is 'fir'.

    :param x: the signal to be downsampled (1D NumPy array)
    :param q: the downsampling factor
    :param n: order of the filter (1 less than the length of the filter for a
         'fir' filter)
    :param ftype: type of the filter; can be 'iir' or 'fir'
    
    :returns: the downsampled signal (1D NumPy array)

    """

    b, a, n = decimate_coeffs(q,n,ftype)
            
    if zi is None or zi is True:
        zi_ = num.zeros(max(len(a),len(b))-1, dtype=num.float)
    else:
        zi_ = zi
    
    y, zf = signal.lfilter(b, a, x, zi=zi_)

    if zi is not None:
        return y[n/2+ioff::q].copy(), zf
    else:
        return y[n/2+ioff::q].copy()
    
class UnavailableDecimation(Exception):
    '''Exception raised by :py:func:`decitab` for unavailable decimation factors.'''

    pass
    
    
    
def gcd(a,b, epsilon=1e-7):
    '''Greatest common divisor.'''
    
    while b > epsilon*a:
       a, b = b, a % b

    return a

def lcm(a,b):
    '''Least common multiple.'''

    return a*b/gcd(a,b)

def mk_decitab(nmax=100):
    '''Make table with decimation sequences.
    
    Decimation from one sampling rate to a lower one is achieved by a successive
    application of :py:func:`decimation` with small integer downsampling 
    factors (because using large downampling factors can make the decimation
    unstable or slow). This function sets up a table with downsample sequences
    for factors up to `nmax`.
    '''

    tab = GlobalVars.decitab
    for i in range(1,10):
        for j in range(1,i+1):
            for k in range(1,j+1):
                for l in range(1,k+1):
                    for m in range(1,l+1):
                        p = i*j*k*l*m
                        if p > nmax: break
                        if p not in tab:
                            tab[p] = (i,j,k,l,m)
                    if i*j*k*l > nmax: break
                if i*j*k > nmax: break
            if i*j > nmax: break
        if i > nmax: break
        
    GlobalVars.decitab_nmax = nmax

def zfmt(n):
    return '%%0%ii' % (int(math.log10(n - 1 )) + 1)
    
def julian_day_of_year(timestamp):
    '''Get the day number after the 1st of January of year in *timestamp*.

    :returns: day number as int
    '''

    return time.gmtime(int(timestamp)).tm_yday

def day_start(timestamp):
    '''Get beginning of day for any point in time.
    
    :param timestamp: time instant as system timestamp (in seconds)

    :returns: instant of day start as system timestamp
    '''

    tt = time.gmtime(int(timestamp))
    tts = tt[0:3] + (0,0,0) + tt[6:9]
    return calendar.timegm(tts)

def month_start(timestamp):
    '''Get beginning of month for any point in time.
    
    :param timestamp: time instant as system timestamp (in seconds)

    :returns: instant of month start as system timestamp
    '''

    tt = time.gmtime(int(timestamp))
    tts = tt[0:2] + (1,0,0,0) + tt[6:9]
    return calendar.timegm(tts)

def year_start(timestamp):
    '''Get beginning of year for any point in time.
    
    :param timestamp: time instant as system timestamp (in seconds)

    :returns: instant of year start as system timestamp
    '''
    
    tt = time.gmtime(int(timestamp))
    tts = tt[0:1] + (1,1,0,0,0) + tt[6:9]
    return calendar.timegm(tts)

def iter_days(tmin, tmax):
    '''Yields begin and end of days until given time span is covered.

    :param tmin,tmax: input time span
    
    :yields: tuples with (begin, end) of days as system timestamps
    '''

    t = day_start(tmin)
    while t < tmax:
        tend = day_start( t + 26*60*60 )
        yield t, tend
        t = tend

def iter_months(tmin, tmax):
    '''Yields begin and end of months until given time span is covered.

    :param tmin,tmax: input time span
    
    :yields: tuples with (begin, end) of months as system timestamps
    '''
    
    t = month_start(tmin)
    while t < tmax:
        tend = month_start(t + 24*60*60*33 )
        yield t, tend
        t = tend

def iter_years(tmin, tmax):
    '''Yields begin and end of years until given time span is covered.

    :param tmin,tmax: input time span
    
    :yields: tuples with (begin, end) of years as system timestamps
    '''
    
    t = year_start(tmin)
    while t < tmax:
        tend = year_start(t + 24*60*60*369 )
        yield t, tend
        t = tend

def decitab(n):
    '''Get integer decimation sequence for given downampling factor.
    
    :param n: target decimation factor
    
    :returns: tuple with downsampling sequence
    '''

    if n > GlobalVars.decitab_nmax:
        mk_decitab(n*2)
    if n not in GlobalVars.decitab: raise UnavailableDecimation('ratio = %g' % n)
    return GlobalVars.decitab[n]

def ctimegm(s, format="%Y-%m-%d %H:%M:%S"):
    '''Convert string representing UTC time to system time.
    
    :param s: string to be interpreted
    :param format: format string passed to :py:func:`strptime`
    
    :returns: system time stamp
        
    Interpretes string with format ``'%Y-%m-%d %H:%M:%S'``, using strptime.
    
    .. note::
       This function is to be replaced by :py:func:`str_to_time`.
    '''

    return calendar.timegm(time.strptime(s, format))

def gmctime(t, format="%Y-%m-%d %H:%M:%S"):
    '''Get string representation from system time, UTC.
    
    Produces string with format ``'%Y-%m-%d %H:%M:%S'``, using strftime.
  
    .. note::
       This function is to be repaced by :py:func:`time_to_str`.'''

    return time.strftime(format, time.gmtime(t))
    
def gmctime_v(t, format="%a, %d %b %Y %H:%M:%S"):
    '''Get string representation from system time, UTC. Same as 
    :py:func:`gmctime` but with a more verbose default format.
    
    .. note::
       This function is to be replaced by :py:func:`time_to_str`.'''
       
    return time.strftime(format, time.gmtime(t))

def gmctime_fn(t, format="%Y-%m-%d_%H-%M-%S"):
    '''Get string representation from system time, UTC. Same as
    :py:func:`gmctime` but with a default usable in filenames.
    
    .. note::
       This function is to be replaced by :py:func:`time_to_str`.'''
       
    return time.strftime(format, time.gmtime(t))

class TimeStrError(Exception):
    pass

class FractionalSecondsMissing(TimeStrError):
    '''Exception raised by :py:func:`str_to_time` when the given string lacks
    fractional seconds.'''
    pass

class FractionalSecondsWrongNumberOfDigits(TimeStrError):
    '''Exception raised by :py:func:`str_to_time` when the given string has an incorrect number of digits in the fractional seconds part.'''
    pass

def _endswith_n(s, endings):
    for ix, x in enumerate(endings):
        if s.endswith(x):
            return ix
    return -1

def str_to_time(s, format='%Y-%m-%d %H:%M:%S.OPTFRAC'):
    '''Convert string representing UTC time to floating point system time.
    
    :param s: string representing UTC time
    :param format: time string format
    :returns: system time stamp as floating point value
    
    Uses the semantics of :py:func:`time.strptime` but allows for fractional seconds.
    If the format ends with ``'.FRAC'``, anything after a dot is interpreted as
    fractional seconds. If the format ends with ``'.OPTFRAC'``, the fractional part,
    including the dot is made optional. The latter has the consequence, that the time 
    strings and the format may not contain any other dots. If the format ends
    with ``'.xFRAC'`` where x is 1, 2, or 3, it is ensured, that exactly that
    number of digits are present in the fractional seconds.
    '''
    if util_ext is not None:
        try:
            t, tfrac = util_ext.stt(s, format)
        except util_ext.UtilExtError, e:
            raise TimeStrError('%s, string=%s, format=%s' % (str(e), s, format))

        return t+tfrac

    fracsec = 0.
    fixed_endings = '.FRAC', '.1FRAC', '.2FRAC', '.3FRAC'
    
    iend = _endswith_n(format, fixed_endings)
    if iend != -1:
        dotpos = s.rfind('.')
        if dotpos == -1:
            raise FractionalSecondsMissing('string=%s, format=%s' % (s,format))
        
        if iend > 0 and iend != (len(s)-dotpos-1):
            raise FractionalSecondsWrongNumberOfDigits('string=%s, format=%s' % (s,format))
        
        format = format[:-len(fixed_endings[iend])]
        fracsec = float(s[dotpos:])
        s = s[:dotpos]
        
    elif format.endswith('.OPTFRAC'):
        dotpos = s.rfind('.')
        format = format[:-8]
        if dotpos != -1 and len(s[dotpos:]) > 1:
            fracsec = float(s[dotpos:])
        
        if dotpos != -1:
            s = s[:dotpos]
      

    try:
        return calendar.timegm(time.strptime(s, format)) + fracsec
    except ValueError, e:
        raise TimeStrError('%s, string=%s, format=%s' % (str(e), s, format))


stt = str_to_time

def time_to_str(t, format='%Y-%m-%d %H:%M:%S.3FRAC'):
    '''Get string representation for floating point system time.
    
    :param t: floating point system time
    :param format: time string format
    :returns: string representing UTC time
    
    Uses the semantics of :py:func:`time.strftime` but additionally allows 
    for fractional seconds. If *format* contains ``'.xFRAC'``, where ``x`` is a digit between 1 and 9, 
    this is replaced with the fractional part of *t* with ``x`` digits precision.
    '''
    
    if isinstance(format, int):
        format = '%Y-%m-%d %H:%M:%S.'+str(format)+'FRAC'

    if util_ext is not None:
        t0 = math.floor(t)
        try:
            return util_ext.tts(int(t0), t - t0, format)
        except util_ext.UtilExtError, e:
            raise TimeStrError('%s, timestamp=%f, format=%s' % (str(e), t, format))
    
    if not GlobalVars.re_frac:
        GlobalVars.re_frac = re.compile(r'\.[1-9]FRAC')
        GlobalVars.frac_formats = dict([  ('.%sFRAC' % x, '%.'+x+'f') for x in '123456789' ] )
    
    ts = float(num.floor(t))
    tfrac = t-ts
    
    m = GlobalVars.re_frac.search(format)
    if m:
        sfrac = (GlobalVars.frac_formats[m.group(0)] % tfrac)
        if sfrac[0] == '1':
            ts += 1.
                        
        format, nsub = GlobalVars.re_frac.subn(sfrac[1:], format, 1)
   
    return time.strftime(format, time.gmtime(ts))

tts = time_to_str
    
def plural_s(n):
    if n == 1:
        return ''
    else:
        return 's' 

def ensuredirs(dst):
    '''Create all intermediate path components for a target path.
    
    :param dst: target path
    
    The leaf part of the target path is not created (use :py:func:`ensuredir` if
    a the target path is a directory to be created).
    '''
    
    d,x = os.path.split(dst)
    dirs = []
    while d and not os.path.exists(d):
        dirs.append(d)
        d,x = os.path.split(d)
        
    dirs.reverse()
    
    for d in dirs:
        if not os.path.exists(d):
            os.mkdir(d)

def ensuredir(dst):
    '''Create directory and all intermediate path components to it as needed.
    
    :param dst: directory name
    
    Nothing is done if the given target already exists.
    '''
    
    if os.path.exists(dst):
        return
        
    ensuredirs(dst)
    os.mkdir(dst)
    
def reuse(x):
    '''Get unique instance of an object.
    
    :param x: hashable object
    :returns: reference to x or an equivalent object
    
    Cache object *x* in a global dict for reuse, or if x already
    is in that dict, return a reference to it.
    
    '''
    grs = GlobalVars.reuse_store
    if not x in grs:
        grs[x] = x
    return grs[x]
    
    
class Anon:
    '''Dict-to-object utility.

    Any given arguments are stored as attributes.

    Example::
    
        a = Anon(x=1, y=2)
        print a.x, a.y
    '''

    def __init__(self, **dict):
        for k in dict:
            self.__dict__[k] = dict[k]


def select_files( paths, selector=None,  regex=None, show_progress=True ):
    '''Recursively select files.
    
    :param paths: entry path names
    :param selector: callback for conditional inclusion
    :param regex: pattern for conditional inclusion
    :param show_progress: if True, indicate start and stop of processing
    :returns: list of path names
    
    Recursively finds all files under given entry points *paths*. If
    parameter *regex* is a regular expression, only files with matching path names
    are included. If additionally parameter *selector*
    is given a callback function, only files for which the callback returns 
    ``True`` are included. The callback should take a single argument. The callback
    is called with a single argument, an object, having as attributes, any named
    groups given in *regex*.
    
    Examples
    
    To find all files ending in ``'.mseed'`` or ``'.msd'``::
    
        select_files(paths,
            regex=r'\.(mseed|msd)$')
        
    To find all files ending with ``'$Year.$DayOfYear'``, having set 2009 for 
    the year::
    
        select_files(paths, 
            regex=r'(?P<year>\d\d\d\d)\.(?P<doy>\d\d\d)$', 
            selector=(lambda x: int(x.year) == 2009))
    '''

    if show_progress:
        progress_beg('selecting files...')
        if logger.isEnabledFor(logging.DEBUG): sys.stderr.write('\n')

    good = []
    if regex: rselector = re.compile(regex)

    def addfile(path):
        if regex:
            logger.debug("looking at filename: '%s'" % path) 
            m = rselector.search(path)
            if m:
                infos = Anon(**m.groupdict())
                logger.debug( "   regex '%s' matches." % regex)
                for k,v in m.groupdict().iteritems():
                    logger.debug( "      attribute '%s' has value '%s'" % (k,v) )
                if selector is None or selector(infos):
                    good.append(os.path.abspath(path))
                
            else:
                logger.debug("   regex '%s' does not match." % regex)
        else:
            good.append(os.path.abspath(path))
        
    if isinstance(paths, str):
        paths = [ paths ]

    for path in paths:
        if os.path.isdir(path):
            for (dirpath, dirnames, filenames) in os.walk(path):
                for filename in filenames:
                    addfile(op.join(dirpath,filename))
        else:
            addfile(path)
   
    if show_progress:    
        progress_end('%i file%s selected.' % (len( good), plural_s(len(good))))
    
    return good

    

def base36encode(number, alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    '''Convert positive integer to a base36 string.'''
    
    if not isinstance(number, (int, long)):
        raise TypeError('number must be an integer')
    if number < 0:
        raise ValueError('number must be positive')
 
    # Special case for small numbers
    if number < 36:
        return alphabet[number]
 
    base36 = ''
    while number != 0:
        number, i = divmod(number, 36)
        base36 = alphabet[i] + base36
 
    return base36
 
def base36decode(number):
    '''Decode base36 endcoded positive integer.'''
    
    return int(number,36)

class UnpackError(Exception):
    '''Exception raised when :py:func:`unpack_fixed` encounters an error.'''
    
    pass

ruler = ''.join([ '%-10i' % i for i in range(8) ]) + '\n' + '0123456789' * 8 + '\n'


def unpack_fixed(format, line, *callargs):
    '''Unpack fixed format string, as produced by many fortran codes.
    
    :param format: format specification
    :param line: string to be processed
    :param callargs: callbacks for callback fields in the format
    
    The format is described by a string of comma-separated fields. Each field
    is defined by a character for the field type followed by the field width. A 
    questionmark
    may be appended to the field description to allow the argument to be optional 
    (The data string is then allowed to be filled with blanks and ``None`` is 
    returned in this case).
    
    The following field types are available:
     
    ====  ================================================================
    Type  Description
    ====  ================================================================
    A     string (full field width is extracted)
    a     string (whitespace at the beginning and the end is removed)
    i     integer value
    f     floating point value
    @     special type, a callback must be given for the conversion
    x     special field type to skip parts of the string
    ====  ================================================================

    '''

    ipos = 0
    values = []
    icall = 0
    for form in format.split(','):
        optional = form[-1] == '?'
        form = form.rstrip('?')
        typ = form[0]
        l = int(form[1:])
        s = line[ipos:ipos+l]
        cast = {'x': None, 'A': str, 'a': lambda x: x.strip(), 'i': int, 'f': float, '@': 'extra'}[typ]
        if cast == 'extra':
            cast = callargs[icall]
            icall +=1
        
        if cast is not None:
            if optional and s.strip() == '':
                values.append(None)
            else:
                try:
                    values.append(cast(s))
                except:
                    mark = [' '] * 80 
                    mark[ipos:ipos+l] = ['^'] * l
                    mark = ''.join(mark)
                    raise UnpackError('Invalid cast to type "%s" at position [%i:%i] of line: \n%s%s\n%s' % (typ, ipos, ipos+l, ruler, line.rstrip(), mark))
                
        ipos += l
    
    return values


_pattern_cache = {}
def _nslc_pattern(pattern):
    if pattern not in _pattern_cache:
        rpattern = re.compile(fnmatch.translate(pattern), re.I)
        _pattern_cache[pattern] = rpattern
    else:
        rpattern = _pattern_cache[pattern]

    return rpattern

def match_nslc(patterns, nslc):
    '''Match network-station-location-channel code against pattern or list of patterns.
    
    :param patterns: pattern or list of patterns
    :param nslc: tuple with (network, station, location, channel) as strings

    :returns: ``True`` if the pattern matches or if any of the given patterns match; or ``False``.

    The patterns may contain shell-style wildcards: \*, ?, [seq], [!seq].

    Example::

        match_nslc('*.HAM3.*.BH?', ('GR','HAM3','','BHZ'))   # -> True        
    
    '''
    
    if isinstance(patterns, str):
        patterns = [ patterns ]
    
    s = '.'.join(nslc)
    for pattern in patterns:
        if _nslc_pattern(pattern).match(s):
            return True

    return False

def match_nslcs(patterns, nslcs):
    '''Get network-station-location-channel codes that match given pattern or any of several given patterns.

    :param patterns: pattern or list of patterns
    :param nslcs: list of (network, station, location, channel) tuples

    See also :py:func:`match_nslc`
    '''

    matching = []
    for nslc in nslcs:
        if match_nslc(patterns, nslc): 
            matching.append(nslc)

    return matching

class SoleError(Exception):
    '''Exception raised by objects of type :py:class:`Sole`, when an concurrent instance is running.'''

    pass

class Sole(object):
   
    '''Use POSIX advisory file locking to ensure that only a single instance of a program is running.
    
    :param pid_path: path to lockfile to be used

    Usage::

        from pyrocko.util import Sole, SoleError, setup_logging
        import os
        
        setup_logging('my_program')

        pid_path =  os.path.join(os.environ['HOME'], '.my_program_lock')
        try:
            sole = Sole(pid_path)

        except SoleError, e:
            logger.fatal( str(e) )
            sys.exit(1)

    '''

    def __init__(self, pid_path):
        self._pid_path = pid_path
        self._other_running = False
        ensuredirs(self._pid_path)
        self._lockfile = None

        try:
            self._lockfile = os.open(self._pid_path, os.O_CREAT | os.O_WRONLY)
        except:
            raise SoleError('Cannot open lockfile (path = %s)' % self._pid_path)

        try:
            fcntl.lockf(self._lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
        except IOError:
            self._other_running = True
            try:
                f = open(self._pid_path, 'r')
                pid = f.read().strip()
                f.close()
            except:
                pid = '?'

            raise SoleError('Other instance is running (pid = %s)' % pid)

        try:
            os.ftruncate(self._lockfile, 0)
            os.write(self._lockfile, '%i\n' % os.getpid())
            os.fsync(self._lockfile)

        except:
            pass # the pid is only stored for user information, so this is allowed to fail
            
    def __del__(self):
        if not self._other_running:
            import os, fcntl
            if self._lockfile is not None:
                fcntl.lockf(self._lockfile, fcntl.LOCK_UN)
                os.close(self._lockfile)
            try:
                os.unlink(self._pid_path)
            except:
                pass


re_escapequotes = re.compile(r"(['\\])")
def escapequotes(s):
    return re_escapequotes.sub(r"\\\1", s)

class TableWriter:
    '''Write table of space separated values to a file.

    :param f: file like object

    Strings containing spaces are quoted on output.
    '''

    def __init__(self, f):
        self._f = f

    def writerow(self, row, minfieldwidths=None):

        '''Write one row of values to underlying file.
        
        :param row: iterable of values
        :param minfieldwidths: minimum field widths for the values

        Each value in in `row` is converted to a string and optionally padded with blanks. The resulting
        strings are output separated with blanks. If any values given are strings and if they contain whitespace,
        they are quoted with single quotes, and any internal single quotes are backslash-escaped.
        '''

        out = []
        
        for i, x in enumerate(row):
            w = 0
            if minfieldwidths and i < len(minfieldwidths):
                w = minfieldwidths[i]
            
            if isinstance(x, str):
                if re.search(r"\s|'", x):
                    x = "'%s'" % escapequotes(x)

                x = x.ljust(w)
            else:
                x = str(x).rjust(w)
            
            out.append(x)

        self._f.write( ' '.join(out).rstrip() + '\n')

class TableReader:
    
    '''Read table of space separated values from a file.
    
    :param f: file-like object

    This uses Pythons shlex module to tokenize lines. Should deal correctly with quoted strings.
    '''

    def __init__(self, f):
        self._f = f
        self.eof = False

    def readrow(self):
        '''Read one row from the underlying file, tokenize it with shlex.
        
        :returns: tokenized line as a list of strings.
        '''

        line = self._f.readline()
        if not line:
            self.eof = True
            return []
        s = shlex.shlex(line, posix=True)
        s.whitespace_split = True
        s.whitespace = ' \t\n\r\f\v' # compatible with re's \s
        row = [] 
        while True:
            x = s.get_token()
            if x is None:
                break
            row.append(x)
            
        return row

def gform( number, significant_digits=3 ):
    '''Pretty print floating point numbers.
    
    Align floating point numbers at the decimal dot.
    
    ::

      |  -d.dde+xxx|
      |  -d.dde+xx |
      |-ddd.       |
      | -dd.d      |
      |  -d.dd     |
      |  -0.ddd    |
      |  -0.0ddd   |
      |  -0.00ddd  |
      |  -d.dde-xx |
      |  -d.dde-xxx|
    ''' 
    
    no_exp_range = (pow(10.,-1), 
                    pow(10.,significant_digits))
    width = significant_digits+significant_digits-1+1+1+5
    
    if (no_exp_range[0] <= abs(number) < no_exp_range[1]) or number == 0.:
        s = ('%#.*g' % (significant_digits, number)).rstrip('0')
    else:
        s = '%.*E' % (significant_digits-1, number)
    s = (' '*(-s.find('.')+(significant_digits+1))+s).ljust(width)
    return s


def human_bytesize(value):
    
    exts = 'Bytes kB MB GB TB PB EB ZB YB'.split()

    if value == 1:
        return '1 Byte'

    for i, ext in enumerate(exts):
        x = float(value) / 1000**i
        if round(x) < 10. and not value < 1000:
            return '%.1f %s' % (x, ext)
        if round(x) < 1000.:
            return '%.0f %s' % (x, ext)

    return '%i Bytes' % value

re_compatibility = re.compile(
    r'!pyrocko\.(trace|gf\.(meta|seismosizer)|fomosto\.(dummy|poel|qseis|qssp))\.'
)

def pf_is_old(fn):
    oldstyle = False
    with open(fn, 'r') as f:
        for line in f:
            if re_compatibility.search(line):
                oldstyle = True

    return oldstyle


def pf_upgrade(fn):
    need = pf_is_old(fn)
    if need:
        fn_temp = fn + '.temp'

        with open(fn, 'r') as fin:
            with open(fn_temp, 'w') as fout:
                for line in fin:
                    line = re_compatibility.sub('!pf.', line)
                    fout.write(line)

        os.rename(fn_temp, fn)

    return need


def read_leap_seconds(tzfile='/usr/share/zoneinfo/right/UTC'):
    '''Extract leap second information from tzdata.
    
    Based on example at http://stackoverflow.com/questions/19332902/\
            extract-historic-leap-seconds-from-tzdata

    See also 'man 5 tzfile'.
    '''
    from struct import unpack, calcsize
    from datetime import datetime
    out = []
    with open(tzfile, 'rb') as f:
        # read header
        fmt = '>4s c 15x 6l'
        (magic, format, ttisgmtcnt, ttisstdcnt, leapcnt, timecnt,
            typecnt, charcnt) =  unpack(fmt, f.read(calcsize(fmt)))
        assert magic == 'TZif'.encode('US-ASCII'), 'Not a timezone file'

        # skip over some uninteresting data
        fmt = '>%(timecnt)dl %(timecnt)dB %(ttinfo)s %(charcnt)ds' % dict(
            timecnt=timecnt, ttinfo='lBB'*typecnt, charcnt=charcnt)
        f.read(calcsize(fmt))

        #read leap-seconds
        fmt = '>2l'
        for i in xrange(leapcnt):
            tleap, nleap = unpack(fmt, f.read(calcsize(fmt)))
            out.append((tleap-nleap+1, nleap))

    return out


class LeapSecondsError(Exception):
    pass


class LeapSecondsOutdated(LeapSecondsError):
    pass


def parse_leap_seconds_list(fn):
    data = []
    texpires = None
    try:
        t0 = int(round(str_to_time('1900-01-01 00:00:00')))
    except TimeStrError:
        t0 = int(round(str_to_time('1970-01-01 00:00:00'))) - 2208988800

    tnow = int(round(time.time()))

    if not op.exists(fn):
        raise LeapSecondsOutdated('no leap seconds file found')

    try:
        with open(fn, 'r') as f:
            for line in f:
                if line.startswith('#@'):
                    texpires = int(line.split()[1])  + t0
                elif line.startswith('#'):
                    pass
                else:
                    toks = line.split()
                    t = int(toks[0]) + t0
                    nleap = int(toks[1]) - 10
                    data.append((t, nleap))

    except IOError:
        raise LeapSecondsError('cannot read leap seconds file %s' % fn)

    if texpires is None or tnow > texpires:
        raise LeapSecondsOutdated('leap seconds list is outdated')

    return data


def read_leap_seconds2():
    from pyrocko import config
    conf = config.config()
    fn = conf.leapseconds_path
    url = conf.leapseconds_url
    try:
        return parse_leap_seconds_list(fn)

    except LeapSecondsOutdated:
        try:
            logger.info('updating leap seconds list...')
            download_file(url, fn)

        except Exception:
            raise LeapSecondsError(
                'cannot download leap seconds list from %s to %s' (url, fn))

        return parse_leap_seconds_list(fn)


def gps_utc_offset(t):
    ls = read_leap_seconds2()
    i = 0
    if t < ls[0][0]:
        return ls[0][1] - 9
    while i < len(ls) - 1:
        if ls[i][0] <= t and t < ls[i+1][0]:
            return ls[i][1] - 9
        i += 1

    return ls[-1][1] - 9


def make_iload_family(iload_fh, doc_fmt='FMT', doc_yielded_objects='FMT'):
    import itertools, glob
    from io_common import FileLoadError

    def iload_filename(filename):
        try:
            with open(filename, 'r') as f:
                for cr in iload_fh(f):
                    yield cr

        except FileLoadError, e:
            e.set_context('filename', filename)
            raise

    def iload_dirname(dirname):
        for entry in os.listdir(dirname):
            fpath = op.join(dirname, entry)
            if op.isfile(fpath):
                for cr in iload_filename(fpath):
                    yield cr

    def iload_glob(pattern):

        fns = glob.glob(pattern)
        for fn in fns:
            for cr in iload_filename(fn):
                yield cr

    def iload(source):
        if isinstance(source, basestring):
            if op.isdir(source):
                return iload_dirname(source)
            elif op.isfile(source):
                return iload_filename(source)
            else:
                return iload_glob(source)

        elif hasattr(source, 'read'):
            return iload_fh(source)
        else:
            return itertools.chain.from_iterable(
                iload(subsource) for subsource in source)

    iload_filename.__doc__ = '''
        Read %s information from named file.
    ''' % doc_fmt

    iload_dirname.__doc__ = '''
        Read %s information from directory of %s files.
    ''' % (doc_fmt, doc_fmt)

    iload_glob.__doc__ = '''
        Read %s information from files matching a glob pattern.
    ''' % doc_fmt

    iload.__doc__ =  '''
        Load %s information from given source(s)

        The *source* can be specified as the name of a %s file, the name of a
        directory containing %s files, a glob pattern of %s files, an open
        filehandle or an iterator yielding any of the forementioned sources.

        This function behaves as a generator yielding %s objects.
    ''' % (doc_fmt, doc_fmt, doc_fmt, doc_fmt, doc_yielded_objects)

    for f in iload_filename, iload_dirname, iload_glob, iload:
        f.__module__ = iload_fh.__module__

    return iload_filename, iload_dirname, iload_glob, iload


class Inconsistency(Exception):
    pass


def consistency_check(list_of_tuples, message='values differ:'):
    '''Check for inconsistencies.

    Given a list of tuples, check that all tuple elements except for first one
    match. E.g. [('STA.N', 55.3, 103.2), ('STA.E', 55.3, 103.2)] would be
    valid because the coordinates at the two channels are the same.'''

    if len(list_of_tuples) >= 2:
        if any(t[1:] != list_of_tuples[0][1:] for t in list_of_tuples[1:]):
            raise Inconsistency('%s\n' % message + '\n'.join(
                '  %s: %s' % (t[0], ','.join('%g' % x for x in t[1:]))
                for t in list_of_tuples))


class defaultzerodict(dict):
    def __missing__(self, k):
        return 0


def mostfrequent(x):
    c = defaultzerodict()
    for e in x:
        c[e] += 1

    return sorted(c.keys(), key=lambda k: c[k])[-1]


def consistency_merge(list_of_tuples,
                      message='values differ:',
                      error='raise',
                      merge=mostfrequent):

    assert error in ('raise', 'warn', 'ignore')

    if len(list_of_tuples) == 0:
        raise Exception('cannot merge empty sequence')

    try:
        consistency_check(list_of_tuples, message)
        return list_of_tuples[0][1:]
    except Inconsistency, e:
        if error == 'raise':
            raise

        elif error == 'warn':
            logger.warn(str(e))

        return tuple([merge(x) for x in zip(*list_of_tuples)[1:]])

